from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tau2.domains.clinic.utils import CLINIC_DB_PATH
from tau2.environment.db import DB

Specialty = Literal[
    "general",
    "dental",
    "dermatology",
    "orthopedics",
    "pediatrics",
    "cardiology",
]
AppointmentType = Literal[
    "checkup",
    "follow_up",
    "consultation",
    "procedure",
    "urgent",
    "vaccination",
]
AppointmentStatus = Literal[
    "scheduled",
    "confirmed",
    "in_progress",
    "completed",
    "cancelled",
    "no_show",
]
ReferralStatus = Literal["pending", "scheduled", "completed", "expired"]
InvoiceStatus = Literal[
    "pending",
    "paid",
    "overdue",
    "payment_plan",
    "insurance_pending",
]
InsuranceStatus = Literal["active", "expired", "pending_verification"]
LabResultStatus = Literal["pending", "completed", "reviewed"]
InvoiceItemCategory = Literal[
    "consultation",
    "procedure",
    "lab",
    "imaging",
    "medication",
]


class Patient(BaseModel):
    patient_id: str = Field(description="Unique identifier for the patient")
    name: str = Field(description="Patient's full name")
    email: str = Field(description="Patient's email address")
    phone: str = Field(description="Patient's phone number")
    dob: str = Field(description="Date of birth (YYYY-MM-DD)")
    address: str = Field(description="Patient's mailing address")
    insurance_id: Optional[str] = Field(None, description="ID of insurance on file")
    emergency_contact: str = Field(description="Emergency contact info")
    allergies: List[str] = Field(default_factory=list, description="Known allergies")
    current_medications: List[str] = Field(
        default_factory=list, description="Current medications"
    )
    primary_doctor_id: Optional[str] = Field(None, description="Primary care doctor ID")
    appointment_ids: List[str] = Field(
        default_factory=list, description="List of appointment IDs"
    )
    balance_due: float = Field(
        default=0.0, description="Outstanding balance in dollars"
    )
    payment_method_ids: List[str] = Field(
        default_factory=list, description="Payment method IDs on file"
    )


class Doctor(BaseModel):
    doctor_id: str = Field(description="Unique identifier for the doctor")
    name: str = Field(description="Doctor's full name")
    clinic_id: str = Field(description="ID of the clinic the doctor works at")
    specialty: Specialty = Field(description="Medical specialty")
    available_days: List[str] = Field(
        description="Days of the week the doctor is available"
    )
    available_hours: str = Field(description="Available hours (e.g. '9:00-17:00')")
    accepting_new_patients: bool = Field(
        description="Whether the doctor is accepting new patients"
    )


class Clinic(BaseModel):
    clinic_id: str = Field(description="Unique identifier for the clinic")
    name: str = Field(description="Clinic name")
    address: str = Field(description="Clinic address")
    phone: str = Field(description="Clinic phone number")
    hours: str = Field(description="Operating hours")
    departments: List[str] = Field(
        default_factory=list, description="Departments available"
    )


class Appointment(BaseModel):
    appointment_id: str = Field(description="Unique identifier for the appointment")
    patient_id: str = Field(description="ID of the patient")
    doctor_id: str = Field(description="ID of the doctor")
    clinic_id: str = Field(description="ID of the clinic")
    date: str = Field(description="Appointment date (YYYY-MM-DD)")
    time: str = Field(description="Appointment time (HH:MM)")
    type: AppointmentType = Field(description="Type of appointment")
    status: AppointmentStatus = Field(description="Current status")
    notes: Optional[str] = Field(None, description="Appointment notes")
    referral_id: Optional[str] = Field(
        None, description="Referral ID if specialist visit"
    )


class Prescription(BaseModel):
    prescription_id: str = Field(description="Unique identifier for the prescription")
    patient_id: str = Field(description="ID of the patient")
    medication: str = Field(description="Medication name")
    dosage: str = Field(description="Dosage instructions")
    frequency: str = Field(description="Frequency (e.g. 'twice daily')")
    start_date: str = Field(description="Prescription start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(
        None, description="Prescription end date (YYYY-MM-DD)"
    )
    refills_remaining: int = Field(default=0, description="Number of refills remaining")
    doctor_id: str = Field(description="Prescribing doctor's ID")
    controlled_substance: bool = Field(
        default=False, description="Whether this is a controlled substance"
    )


class Referral(BaseModel):
    referral_id: str = Field(description="Unique identifier for the referral")
    patient_id: str = Field(description="ID of the patient")
    referring_doctor_id: str = Field(description="ID of the referring doctor")
    specialist_doctor_id: Optional[str] = Field(
        None, description="ID of the specialist doctor"
    )
    specialty: Specialty = Field(description="Specialty the patient is referred to")
    reason: str = Field(description="Reason for the referral")
    status: ReferralStatus = Field(description="Current referral status")
    expiry_date: str = Field(description="Referral expiration date (YYYY-MM-DD)")


class InvoiceItem(BaseModel):
    description: str = Field(description="Description of the charge")
    amount: float = Field(description="Charge amount in dollars")
    category: InvoiceItemCategory = Field(description="Charge category")
    insurance_code: Optional[str] = Field(None, description="Insurance billing code")


class Invoice(BaseModel):
    invoice_id: str = Field(description="Unique identifier for the invoice")
    patient_id: str = Field(description="ID of the patient")
    appointment_id: Optional[str] = Field(None, description="Associated appointment ID")
    items: List[InvoiceItem] = Field(
        default_factory=list, description="Line items on the invoice"
    )
    insurance_covered: float = Field(
        default=0.0, description="Amount covered by insurance"
    )
    patient_responsibility: float = Field(
        default=0.0, description="Amount patient owes"
    )
    total: float = Field(default=0.0, description="Total invoice amount")
    status: InvoiceStatus = Field(description="Invoice status")
    due_date: str = Field(description="Payment due date (YYYY-MM-DD)")


class Insurance(BaseModel):
    insurance_id: str = Field(description="Unique identifier for the insurance record")
    patient_id: str = Field(description="ID of the patient")
    provider: str = Field(description="Insurance provider name")
    plan_name: str = Field(description="Plan name")
    group_number: str = Field(description="Group number")
    member_id: str = Field(description="Member ID")
    copay: float = Field(description="Copay amount in dollars")
    deductible: float = Field(description="Annual deductible amount")
    deductible_met: float = Field(
        default=0.0, description="Amount of deductible met so far"
    )
    in_network_clinics: List[str] = Field(
        default_factory=list, description="Clinic IDs in network"
    )
    status: InsuranceStatus = Field(description="Insurance status")


class LabResult(BaseModel):
    result_id: str = Field(description="Unique identifier for the lab result")
    patient_id: str = Field(description="ID of the patient")
    test_name: str = Field(description="Name of the test")
    ordered_by: str = Field(description="Doctor ID who ordered the test")
    date: str = Field(description="Date the test was performed (YYYY-MM-DD)")
    status: LabResultStatus = Field(description="Result status")
    results_summary: Optional[str] = Field(
        None, description="Results summary (only visible to clinical staff)"
    )


class PaymentMethod(BaseModel):
    payment_method_id: str = Field(
        description="Unique identifier for the payment method"
    )
    patient_id: str = Field(description="ID of the patient")
    type: str = Field(description="Payment type (credit_card, debit_card, hsa)")
    last_four: str = Field(description="Last four digits of the card")


class ClinicDB(DB):
    """Multi-location clinic database."""

    patients: Dict[str, Patient] = Field(description="Patients indexed by patient ID")
    doctors: Dict[str, Doctor] = Field(description="Doctors indexed by doctor ID")
    clinics: Dict[str, Clinic] = Field(description="Clinics indexed by clinic ID")
    appointments: Dict[str, Appointment] = Field(
        description="Appointments indexed by appointment ID"
    )
    prescriptions: Dict[str, Prescription] = Field(
        description="Prescriptions indexed by prescription ID"
    )
    referrals: Dict[str, Referral] = Field(
        description="Referrals indexed by referral ID"
    )
    invoices: Dict[str, Invoice] = Field(description="Invoices indexed by invoice ID")
    insurance: Dict[str, Insurance] = Field(
        description="Insurance records indexed by insurance ID"
    )
    lab_results: Dict[str, LabResult] = Field(
        description="Lab results indexed by result ID"
    )
    payment_methods: Dict[str, PaymentMethod] = Field(
        description="Payment methods indexed by payment method ID"
    )

    def get_statistics(self) -> dict[str, Any]:
        return {
            "num_patients": len(self.patients),
            "num_doctors": len(self.doctors),
            "num_clinics": len(self.clinics),
            "num_appointments": len(self.appointments),
            "num_prescriptions": len(self.prescriptions),
            "num_referrals": len(self.referrals),
            "num_invoices": len(self.invoices),
            "num_insurance": len(self.insurance),
            "num_lab_results": len(self.lab_results),
        }


def get_db():
    return ClinicDB.load(CLINIC_DB_PATH)
