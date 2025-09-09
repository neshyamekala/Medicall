import streamlit as st
import requests

# Configuration - This is where your FastAPI backend is running
API_BASE_URL = "http://localhost:8000"  # Change this if you deploy your backend online

st.set_page_config(page_title="CareCard", page_icon="💊", layout="wide")
st.title("💊 CareCard - Smart Medicine Reminder")
st.markdown("---")

# Initialize session state for patient data if it doesn't exist
if 'patients' not in st.session_state:
    st.session_state.patients = []

menu = st.sidebar.selectbox("Navigation", ["🏠 Dashboard", "👵 Register Patient", "💊 Add Medicine", "Simulate Reply","View Data"])

if menu == "🏠 Dashboard":
    st.header("CareCrew Dashboard")
    st.info("""
    **Welcome to CareCard!**
    This dashboard allows you to:
    - Register elderly patients who need medicine reminders.
    - Schedule their medicines.
    - View their adherence status. (Coming Soon)
    """)
    if st.button("Check API Connection"):
        try:
            response = requests.get(f"{API_BASE_URL}/")
            st.success(f"✅ Backend is running! {response.json()['message']}")
        except:
            st.error("❌ Could not connect to the backend. Is `uvicorn app:app --reload` running?")

elif menu == "👵 Register Patient":
    st.header("Register a New Patient")
    with st.form("patient_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name", placeholder="e.g., Suresh Kumar")
            phone = st.text_input("Patient's Phone Number", placeholder="e.g., 919876543210", help="Enter 10 digit Indian number. Do not add +91 or 0.")
        with col2:
            language = st.selectbox("Preferred Language for Alerts", ("en", "hi", "te", "ta", "ml"), help="Reminders will be sent in this language.")
            caretaker_phone = st.text_input("Caretaker's Phone Number (Optional)", placeholder="e.g., 919812345670", help="For emergency alerts if medicine is missed.")

        submitted = st.form_submit_button("Register Patient")

    if submitted:
        if not name or not phone:
            st.error("Please fill in at least the Name and Patient's Phone Number.")
        else:
            # Prepare the data to send to our FastAPI backend
            params = {
                "phone": phone,
                "name": name,
                "language": language,
                "caretaker_phone": caretaker_phone if caretaker_phone else None
            }
            try:
                response = requests.post(f"{API_BASE_URL}/patient/", params=params)
                if response.status_code == 200:
                    st.success(f"✅ Patient '{name}' registered successfully!")
                else:
                    st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to the backend server. Please make sure it's running.")

elif menu == "Simulate Reply":
    st.header("Simulate Patient SMS Reply")
    st.warning("Use this to simulate a patient replying to a reminder via SMS.")

    patient_phone_sim = st.text_input("Patient's Phone Number", key="sim_phone", placeholder="e.g., 9542269026")
    response = st.selectbox("Patient's Response", ["TAKEN", "SKIPPED"])

    if st.button("Submit Simulated Reply"):
        if patient_phone_sim:
            # This will call your new webhook endpoint directly
            try:
                response = requests.post(f"{API_BASE_URL}/webhook/sms", data={
                    "From": f"+91{patient_phone_sim}",
                    "Body": response
                })
                if response.status_code == 200:
                    st.success(f"Simulated reply '{response}' recorded for {patient_phone_sim}!")
                else:
                    st.error("Error simulating reply.")
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the backend server.")
        else:
            st.error("Please enter a phone number.")

elif menu == "💊 Add Medicine":
    st.header("Add a Medicine Schedule")
    patient_phone_for_med = st.text_input("Patient's Registered Phone Number", key="med_phone", placeholder="Enter the phone number used to register the patient")
    
    if patient_phone_for_med:
        with st.form("medicine_form"):
            med_name = st.text_input("Medicine Name", placeholder="e.g., Metformin")
            dosage = st.text_input("Dosage", placeholder="e.g., 1 Tablet")
            
            # MANUAL TIME INPUT - REPLACED THE DROPDOWN
            time = st.text_input(
                "Time to take medicine (HH:MM)",
                placeholder="e.g., 08:30, 14:00, 22:15",
                help="Enter the time in 24-hour format. Example: 13:30 for 1:30 PM."
            )
            
            submitted_med = st.form_submit_button("Add Medicine Schedule")

        if submitted_med:
            # Input validation for the manually typed time
            if not med_name or not dosage or not time:
                st.error("Please fill in Medicine Name, Dosage, and Time.")
            elif not (len(time) == 5 and time[2] == ':' and time[:2].isdigit() and time[3:].isdigit()):
                st.error("❌ Please enter time in the correct HH:MM format (e.g., 08:30 or 14:00).")
            else:
                params = {
                    "name": med_name,
                    "dosage": dosage,
                    "time": time
                }
                try:
                    # Call the endpoint: /patient/{phone}/medicine/
                    response = requests.post(f"{API_BASE_URL}/patient/{patient_phone_for_med}/medicine/", params=params)
                    if response.status_code == 200:
                        st.success(f"✅ Medicine '{med_name}' scheduled for {time} successfully!")
                    else:
                        st.error(f"Error: {response.json().get('detail', 'Patient not found or other error')}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Could not connect to the backend server.")

elif menu == "View Data":
    st.header("View Patient Data")
    st.info("This feature would require building more API endpoints to get data from Firestore. For the prototype, you can view your data directly in the [Firebase Console](https://console.firebase.google.com/).")