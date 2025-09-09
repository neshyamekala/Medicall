from fastapi import FastAPI, HTTPException, Request, Form
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import communications as comm
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

app = FastAPI(title="CareCard API", description="Backend for the CareCard Project")

def check_medicines():
    """Scheduled task to run every minute. This is the brain of the operation."""
    print(f"[Scheduler] Checking for due medicines at {datetime.now().strftime('%H:%M:%S')}")
    current_time = datetime.now().strftime("%H:%M")  # Get current time in "HH:MM"

    # 1. Get all patients
    try:
        patients_ref = db.collection('patients')
        patients = patients_ref.stream()

        for patient_doc in patients:
            patient_data = patient_doc.to_dict()
            patient_id = patient_doc.id
            print(f"[Scheduler] Checking patient: {patient_data.get('name')}")

            # 2. Check their 'medicines' sub-collection
            meds_ref = patients_ref.document(patient_id).collection('medicines')
            # Let's assume for the prototype, we get all medicines. You can later add 'is_active'
            medicines = meds_ref.stream()

            for med in medicines:
                med_data = med.to_dict()
                if med_data.get('time') == current_time:  # It's time for this medicine!
                    print(f"[Scheduler] Time for {med_data['name']} for {patient_data.get('name')}")
                    # Call the function in communications.py to send the reminder
                    comm.send_reminder(patient_id, patient_data, med_data)
    except Exception as e:
        print(f"[Scheduler] An error occurred: {e}")

# Start the scheduler
# This is a very important part. It runs the check_medicines function every minute.
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=check_medicines,
    trigger=IntervalTrigger(minutes=1),
    id='medicine_check_job',
    name='Check for due medicines every minute',
    replace_existing=True)
scheduler.start()
print("Scheduler started! Checking for medicines every minute.")

# API Endpoints for Streamlit Dashboard to use
@app.get("/")
async def root():
    return {"message": "Welcome to the CareCard API! The scheduler is running."}

@app.post("/patient/")
async def create_patient(phone: str, name: str, language: str = "en", caretaker_phone: str = None):
    try:
        doc_ref = db.collection('patients').document(phone)
        doc_ref.set({
            'name': name,
            'phone': phone,
            'language': language,
            'caretaker_phone': caretaker_phone,
            'last_response': 'pending'  # Initialize response status
        })
        return {"message": f"Patient {name} added successfully!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/patient/{patient_phone}/medicine/")
async def add_medicine(patient_phone: str, name: str, dosage: str, time: str):
    try:
        # Check if patient exists
        patient_ref = db.collection('patients').document(patient_phone)
        if not patient_ref.get().exists:
            raise HTTPException(status_code=404, detail="Patient not found")

        med_ref = patient_ref.collection('medicines').document()
        med_ref.set({
            'name': name,
            'dosage': dosage,
            'time': time  # e.g., "08:00"
        })
        return {"message": f"Medicine {name} added for patient {patient_phone}!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/webhook/sms")
async def receive_sms_response(From: str = Form(...), Body: str = Form(...)):
    """This endpoint receives SMS replies from patients via Twilio."""
    try:
        # Extract the phone number (remove '+91' if present)
        phone_number = From.replace("+91", "") 
        body = Body.strip().upper()
        
        # Get the patient's document from Firestore
        patient_ref = db.collection('patients').document(phone_number)
        patient = patient_ref.get()
        
        if not patient.exists:
            return {"message": "Patient not found"}
        
        # Update status based on response
        if body == "TAKEN":
            status = "taken"
        elif body == "SKIPPED":
            status = "skipped"
        else:
            status = "invalid_response"
        
        # Update the patient's status in database
        patient_ref.update({
            'last_response': status,
            'last_response_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return {"message": f"Status updated to {status}"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhook/voice")
async def handle_voice_response(request: Request):
    """Handles DTMF responses from voice calls (1 for taken, 2 for skipped)."""
    try:
        form_data = await request.form()
        digits = form_data.get('Digits')
        from_number = form_data.get('From')
        
        if digits and from_number:
            phone_number = from_number.replace("+91", "")
            status = "taken" if digits == "1" else "skipped"
            
            # Update the patient's status in database
            patient_ref = db.collection('patients').document(phone_number)
            if patient_ref.get().exists:
                patient_ref.update({
                    'last_response': status,
                    'last_response_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                print(f"Voice response recorded: {status} for {phone_number}")
                return {"message": "Response recorded successfully"}
        
        return {"message": "No valid response received"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def check_missed_medicines():
    """Check if patients didn't respond to reminders"""
    print("Checking for missed medicine responses...")
    
    patients_ref = db.collection('patients')
    patients = patients_ref.stream()
    
    for patient_doc in patients:
        patient_data = patient_doc.to_dict()
        
        # Check if patient has a pending reminder (no response)
        if patient_data.get('last_response') == 'pending':
            caretaker_phone = patient_data.get('caretaker_phone')
            if caretaker_phone:
                # Send alert to caretaker
                alert_message = f"Alert: {patient_data['name']} may have missed their medicine. Please check."
                comm.send_caretaker_alert(caretaker_phone, alert_message)
                print(f"Alert sent to caretaker: {caretaker_phone}")

# Add the missed medicines checker to the scheduler
scheduler.add_job(
    func=check_missed_medicines,
    trigger=IntervalTrigger(minutes=15),  # Check every 15 minutes
    id='missed_medicines_job',
    name='Check for missed medicines every 15 minutes',
    replace_existing=True)

# Run the server with: uvicorn app:app --reload --host 0.0.0.0 --port 8000