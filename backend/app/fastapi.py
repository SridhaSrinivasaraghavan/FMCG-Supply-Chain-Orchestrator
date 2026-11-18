from fastapi import FastAPI
from pydantic import BaseModel
app=FastAPI()
class PatientMessage(BaseModel):
    patient_message: str
@app.post("/patient-message")
async def receive_patient_message(patient: PatientMessage):
    return {
    "status": "success",
    "received_message": patient.patient_message,
    "message": "Patient message received successfully"
}