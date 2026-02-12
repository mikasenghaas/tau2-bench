from datetime import datetime, timedelta
from typing import Optional

from tau2.domains.clinic.data_model import (
    Appointment,
    ClinicDB,
    Doctor,
    Insurance,
    Invoice,
    InvoiceItem,
    LabResult,
    Patient,
    PaymentMethod,
    Prescription,
    Referral,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool

# Fixed reference date — must match generate_db.py / generate_tasks.py TODAY.
REFERENCE_DATE = datetime(2025, 10, 15)

# Policy constants
CANCELLATION_FEE_24H = 50.0
CANCELLATION_FEE_4H = 100.0
PRESCRIPTION_VISIT_WINDOW_MONTHS = 12
REFERRAL_EXPIRY_DAYS = 90
PAYMENT_PLAN_MIN_BALANCE = 500.0
PAYMENT_PLAN_MAX_INSTALLMENTS = 6
MAX_URGENT_PER_DOCTOR_PER_DAY = 2


class ClinicTools(ToolKitBase):
    """Tools for the clinic domain."""

    db: ClinicDB

    def __init__(self, db: ClinicDB) -> None:
        super().__init__(db)

    # ── ID helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _make_unique_id(base: str, existing) -> str:
        if base not in existing:
            return base
        n = 2
        while f"{base}_{n}" in existing:
            n += 1
        return f"{base}_{n}"

    def _patient_last(self, patient_id: str) -> str:
        return self.db.patients[patient_id].name.split()[-1].lower()

    # ── READ tools ────────────────────────────────────────────────────────

    @is_tool(ToolType.READ)
    def find_patient_by_name_dob(self, name: str, dob: str) -> list[Patient]:
        """
        Find patients by name and date of birth. Name is case-insensitive
        partial match; DOB must match exactly.

        Args:
            name: The name to search for
            dob: Date of birth (YYYY-MM-DD)

        Returns:
            A list of matching patients
        """
        name_lower = name.lower()
        return [
            p
            for p in self.db.patients.values()
            if name_lower in p.name.lower() and p.dob == dob
        ]

    @is_tool(ToolType.READ)
    def find_patient_by_phone(self, phone: str) -> list[Patient]:
        """
        Find patients by phone number (exact match).

        Args:
            phone: The phone number to search for

        Returns:
            A list of matching patients
        """
        return [p for p in self.db.patients.values() if p.phone == phone]

    @is_tool(ToolType.READ)
    def get_patient_details(self, patient_id: str) -> Patient:
        """
        Get the full record for a patient.

        Args:
            patient_id: The ID of the patient

        Returns:
            The patient record

        Raises:
            ValueError: If the patient is not found
        """
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")
        return self.db.patients[patient_id]

    @is_tool(ToolType.READ)
    def get_doctor_details(self, doctor_id: str) -> Doctor:
        """
        Get a doctor's profile and availability.

        Args:
            doctor_id: The ID of the doctor

        Returns:
            The doctor record

        Raises:
            ValueError: If the doctor is not found
        """
        if doctor_id not in self.db.doctors:
            raise ValueError(f"Doctor {doctor_id} not found")
        return self.db.doctors[doctor_id]

    @is_tool(ToolType.READ)
    def search_doctors(
        self,
        clinic_id: Optional[str] = None,
        specialty: Optional[str] = None,
        accepting_new: Optional[bool] = None,
    ) -> list[Doctor]:
        """
        Search for doctors by clinic, specialty, and whether they accept new patients.

        Args:
            clinic_id: Optional clinic ID to filter by
            specialty: Optional specialty to filter by (e.g. 'general', 'dental', 'dermatology', 'orthopedics', 'pediatrics', 'cardiology')
            accepting_new: Optional filter for doctors accepting new patients

        Returns:
            A list of matching doctors
        """
        results = list(self.db.doctors.values())
        if clinic_id:
            results = [d for d in results if d.clinic_id == clinic_id]
        if specialty:
            spec_lower = specialty.lower()
            results = [d for d in results if spec_lower in d.specialty.lower()]
        if accepting_new is not None:
            results = [d for d in results if d.accepting_new_patients == accepting_new]
        return results

    @is_tool(ToolType.READ)
    def search_availability(
        self,
        clinic_id: str,
        specialty: Optional[str] = None,
        doctor_id: Optional[str] = None,
        date_range: Optional[str] = None,
        appointment_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Find open appointment slots at a clinic. Returns available time slots
        for doctors matching the criteria.

        Args:
            clinic_id: The ID of the clinic
            specialty: Optional specialty to filter by
            doctor_id: Optional specific doctor ID
            date_range: Optional date range (e.g. '2025-10-15 to 2025-10-22')
            appointment_type: Optional appointment type filter

        Returns:
            A list of available slots (doctor_id, doctor_name, date, time, specialty)

        Raises:
            ValueError: If the clinic is not found
        """
        if clinic_id not in self.db.clinics:
            raise ValueError(f"Clinic {clinic_id} not found")

        doctors = [d for d in self.db.doctors.values() if d.clinic_id == clinic_id]
        if specialty:
            spec_lower = specialty.lower()
            doctors = [d for d in doctors if spec_lower in d.specialty.lower()]
        if doctor_id:
            doctors = [d for d in doctors if d.doctor_id == doctor_id]

        today = REFERENCE_DATE
        start_date = today
        end_date = today + timedelta(days=14)
        if date_range:
            try:
                parts = date_range.split(" to ")
                start_date = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
                end_date = datetime.strptime(parts[1].strip(), "%Y-%m-%d")
            except (IndexError, ValueError):
                pass
        # Never return slots in the past
        if start_date < today:
            start_date = today

        # Collect existing appointments to find occupied slots
        booked: set[tuple[str, str, str]] = set()
        for appt in self.db.appointments.values():
            if appt.status not in ("cancelled", "no_show", "completed"):
                booked.add((appt.doctor_id, appt.date, appt.time))

        slots = []
        day = start_date
        while day <= end_date:
            day_name = day.strftime("%A")
            date_str = day.strftime("%Y-%m-%d")
            for doc in doctors:
                if day_name not in doc.available_days:
                    continue
                try:
                    start_h, end_h = doc.available_hours.split("-")
                    sh = int(start_h.split(":")[0])
                    eh = int(end_h.split(":")[0])
                except (ValueError, IndexError):
                    continue
                for hour in range(sh, eh):
                    time_str = f"{hour:02d}:00"
                    if (doc.doctor_id, date_str, time_str) not in booked:
                        slots.append(
                            {
                                "doctor_id": doc.doctor_id,
                                "doctor_name": doc.name,
                                "specialty": doc.specialty,
                                "date": date_str,
                                "time": time_str,
                            }
                        )
            day += timedelta(days=1)

        return slots

    @is_tool(ToolType.READ)
    def get_appointment(self, appointment_id: str) -> Appointment:
        """
        Get details for a specific appointment.

        Args:
            appointment_id: The ID of the appointment

        Returns:
            The appointment record

        Raises:
            ValueError: If the appointment is not found
        """
        if appointment_id not in self.db.appointments:
            raise ValueError(f"Appointment {appointment_id} not found")
        return self.db.appointments[appointment_id]

    @is_tool(ToolType.READ)
    def list_patient_appointments(self, patient_id: str) -> list[Appointment]:
        """
        List all appointments for a patient (upcoming and past).

        Args:
            patient_id: The ID of the patient

        Returns:
            A list of appointments for the patient

        Raises:
            ValueError: If the patient is not found
        """
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")
        patient = self.db.patients[patient_id]
        return [
            self.db.appointments[aid]
            for aid in patient.appointment_ids
            if aid in self.db.appointments
        ]

    @is_tool(ToolType.READ)
    def get_prescription(self, prescription_id: str) -> Prescription:
        """
        Get details for a specific prescription.

        Args:
            prescription_id: The ID of the prescription

        Returns:
            The prescription record

        Raises:
            ValueError: If the prescription is not found
        """
        if prescription_id not in self.db.prescriptions:
            raise ValueError(f"Prescription {prescription_id} not found")
        return self.db.prescriptions[prescription_id]

    @is_tool(ToolType.READ)
    def list_patient_prescriptions(self, patient_id: str) -> list[Prescription]:
        """
        List all active prescriptions for a patient.

        Args:
            patient_id: The ID of the patient

        Returns:
            A list of active prescriptions

        Raises:
            ValueError: If the patient is not found
        """
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")
        today = REFERENCE_DATE.strftime("%Y-%m-%d")
        return [
            rx
            for rx in self.db.prescriptions.values()
            if rx.patient_id == patient_id
            and (rx.end_date is None or rx.end_date >= today)
        ]

    @is_tool(ToolType.READ)
    def get_referral(self, referral_id: str) -> Referral:
        """
        Get details for a specific referral.

        Args:
            referral_id: The ID of the referral

        Returns:
            The referral record

        Raises:
            ValueError: If the referral is not found
        """
        if referral_id not in self.db.referrals:
            raise ValueError(f"Referral {referral_id} not found")
        return self.db.referrals[referral_id]

    @is_tool(ToolType.READ)
    def get_invoice(self, invoice_id: str) -> Invoice:
        """
        Get details for a specific invoice.

        Args:
            invoice_id: The ID of the invoice

        Returns:
            The invoice record

        Raises:
            ValueError: If the invoice is not found
        """
        if invoice_id not in self.db.invoices:
            raise ValueError(f"Invoice {invoice_id} not found")
        return self.db.invoices[invoice_id]

    @is_tool(ToolType.READ)
    def list_patient_invoices(self, patient_id: str) -> list[Invoice]:
        """
        List all outstanding invoices for a patient.

        Args:
            patient_id: The ID of the patient

        Returns:
            A list of outstanding invoices

        Raises:
            ValueError: If the patient is not found
        """
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")
        return [
            inv
            for inv in self.db.invoices.values()
            if inv.patient_id == patient_id
            and inv.status
            in ("pending", "overdue", "payment_plan", "insurance_pending")
        ]

    @is_tool(ToolType.READ)
    def get_insurance_details(self, insurance_id: str) -> Insurance:
        """
        Get insurance coverage information.

        Args:
            insurance_id: The ID of the insurance record

        Returns:
            The insurance record

        Raises:
            ValueError: If the insurance record is not found
        """
        if insurance_id not in self.db.insurance:
            raise ValueError(f"Insurance {insurance_id} not found")
        return self.db.insurance[insurance_id]

    @is_tool(ToolType.READ)
    def get_lab_results(self, patient_id: str) -> list[dict]:
        """
        Get lab result statuses for a patient. Returns test name, date, and
        status only. Cannot share detailed results — patient must access the
        portal or speak with their doctor.

        Args:
            patient_id: The ID of the patient

        Returns:
            A list of lab result summaries (result_id, test_name, date, status)

        Raises:
            ValueError: If the patient is not found
        """
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")
        return [
            {
                "result_id": lr.result_id,
                "test_name": lr.test_name,
                "date": lr.date,
                "status": lr.status,
            }
            for lr in self.db.lab_results.values()
            if lr.patient_id == patient_id
        ]

    # ── WRITE tools ───────────────────────────────────────────────────────

    @is_tool(ToolType.WRITE)
    def book_appointment(
        self,
        patient_id: str,
        doctor_id: str,
        clinic_id: str,
        date: str,
        time: str,
        appointment_type: str,
    ) -> Appointment:
        """
        Schedule an appointment.

        Args:
            patient_id: The ID of the patient
            doctor_id: The ID of the doctor
            clinic_id: The ID of the clinic
            date: Appointment date (YYYY-MM-DD)
            time: Appointment time (HH:MM)
            appointment_type: Type of appointment (checkup, follow_up, consultation, procedure, urgent, vaccination)

        Returns:
            The new appointment record

        Raises:
            ValueError: If patient/doctor/clinic not found, slot unavailable,
                        or specialist visit without referral
        """
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")
        if doctor_id not in self.db.doctors:
            raise ValueError(f"Doctor {doctor_id} not found")
        if clinic_id not in self.db.clinics:
            raise ValueError(f"Clinic {clinic_id} not found")

        # Reject dates in the past
        today_str = REFERENCE_DATE.strftime("%Y-%m-%d")
        if date < today_str:
            raise ValueError(
                f"Cannot book an appointment in the past. "
                f"The date {date} is before today ({today_str})."
            )

        doctor = self.db.doctors[doctor_id]
        patient = self.db.patients[patient_id]

        # Check specialist referral requirement
        if doctor.specialty != "general" and appointment_type != "urgent":
            has_valid_referral = any(
                ref.patient_id == patient_id
                and ref.specialty == doctor.specialty
                and ref.status in ("pending", "scheduled")
                and ref.expiry_date >= REFERENCE_DATE.strftime("%Y-%m-%d")
                for ref in self.db.referrals.values()
            )
            if not has_valid_referral:
                raise ValueError(
                    f"Specialist appointment with {doctor.specialty} requires "
                    f"a valid referral. Please request a referral from the "
                    f"patient's primary care doctor first."
                )

        # Check insurance for non-urgent appointments
        if appointment_type != "urgent" and patient.insurance_id:
            ins = self.db.insurance.get(patient.insurance_id)
            if ins and ins.status != "active":
                raise ValueError(
                    f"Patient's insurance status is '{ins.status}'. "
                    f"Insurance must be verified before non-urgent appointments. "
                    f"Unverified insurance is treated as self-pay."
                )

        # Check urgent appointment limit
        if appointment_type == "urgent":
            urgent_count = sum(
                1
                for a in self.db.appointments.values()
                if a.doctor_id == doctor_id
                and a.date == date
                and a.type == "urgent"
                and a.status not in ("cancelled", "no_show")
            )
            if urgent_count >= MAX_URGENT_PER_DOCTOR_PER_DAY:
                raise ValueError(
                    f"Doctor {doctor.name} has reached the maximum of "
                    f"{MAX_URGENT_PER_DOCTOR_PER_DAY} urgent appointments for {date}."
                )

        # Check slot availability
        existing = any(
            a.doctor_id == doctor_id
            and a.date == date
            and a.time == time
            and a.status not in ("cancelled", "no_show")
            for a in self.db.appointments.values()
        )
        if existing:
            raise ValueError(
                f"Time slot {date} {time} is not available for Dr. {doctor.name}."
            )

        base_aid = f"appt_{self._patient_last(patient_id)}_{date.replace('-', '')}"
        appointment_id = self._make_unique_id(base_aid, self.db.appointments)
        appointment = Appointment(
            appointment_id=appointment_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            date=date,
            time=time,
            type=appointment_type,
            status="scheduled",
        )

        self.db.appointments[appointment_id] = appointment
        patient.appointment_ids.append(appointment_id)

        # Mark referral as scheduled if applicable
        if doctor.specialty != "general":
            for ref in self.db.referrals.values():
                if (
                    ref.patient_id == patient_id
                    and ref.specialty == doctor.specialty
                    and ref.status == "pending"
                ):
                    ref.status = "scheduled"
                    break

        return appointment

    @is_tool(ToolType.WRITE)
    def reschedule_appointment(
        self, appointment_id: str, date: str, time: str
    ) -> Appointment:
        """
        Reschedule an existing appointment to a new date and time.

        Args:
            appointment_id: The ID of the appointment
            date: New appointment date (YYYY-MM-DD)
            time: New appointment time (HH:MM)

        Returns:
            The updated appointment record

        Raises:
            ValueError: If appointment not found, already completed/cancelled,
                        or new slot not available
        """
        if appointment_id not in self.db.appointments:
            raise ValueError(f"Appointment {appointment_id} not found")

        appt = self.db.appointments[appointment_id]
        if appt.status in ("completed", "cancelled", "no_show"):
            raise ValueError(
                f"Cannot reschedule appointment with status '{appt.status}'."
            )

        # Check new slot
        existing = any(
            a.doctor_id == appt.doctor_id
            and a.date == date
            and a.time == time
            and a.status not in ("cancelled", "no_show")
            and a.appointment_id != appointment_id
            for a in self.db.appointments.values()
        )
        if existing:
            raise ValueError(
                f"Time slot {date} {time} is not available for this doctor."
            )

        appt.date = date
        appt.time = time
        appt.status = "scheduled"
        return appt

    @is_tool(ToolType.WRITE)
    def cancel_appointment(self, appointment_id: str, reason: str) -> Appointment:
        """
        Cancel an appointment. Cancellations less than 24 hours before incur
        a $50 fee; less than 4 hours or no-show incurs $100.

        Args:
            appointment_id: The ID of the appointment
            reason: Reason for cancellation

        Returns:
            The updated appointment record

        Raises:
            ValueError: If appointment not found or already completed/cancelled
        """
        if appointment_id not in self.db.appointments:
            raise ValueError(f"Appointment {appointment_id} not found")

        appt = self.db.appointments[appointment_id]
        if appt.status in ("completed", "cancelled"):
            raise ValueError(f"Cannot cancel appointment with status '{appt.status}'.")

        # Calculate cancellation fee
        appt_dt = datetime.strptime(f"{appt.date} {appt.time}", "%Y-%m-%d %H:%M")
        hours_until = (appt_dt - REFERENCE_DATE).total_seconds() / 3600
        fee = 0.0
        if hours_until < 4:
            fee = CANCELLATION_FEE_4H
        elif hours_until < 24:
            fee = CANCELLATION_FEE_24H

        appt.status = "cancelled"
        appt.notes = f"Cancelled: {reason}"

        if fee > 0:
            patient = self.db.patients[appt.patient_id]
            patient.balance_due += fee
            base_iid = f"inv_cancel_{self._patient_last(appt.patient_id)}_{appt.date.replace('-', '')}"
            inv_id = self._make_unique_id(base_iid, self.db.invoices)
            invoice = Invoice(
                invoice_id=inv_id,
                patient_id=appt.patient_id,
                appointment_id=appointment_id,
                items=[
                    InvoiceItem(
                        description=f"Late cancellation fee",
                        amount=fee,
                        category="consultation",
                    )
                ],
                insurance_covered=0.0,
                patient_responsibility=fee,
                total=fee,
                status="pending",
                due_date=(REFERENCE_DATE + timedelta(days=30)).strftime("%Y-%m-%d"),
            )
            self.db.invoices[inv_id] = invoice

        return appt

    @is_tool(ToolType.WRITE)
    def refill_prescription(self, prescription_id: str) -> Prescription:
        """
        Process a prescription refill. Patient must have been seen in the last
        12 months. Controlled substances cannot be refilled by phone.

        Args:
            prescription_id: The ID of the prescription

        Returns:
            The updated prescription record

        Raises:
            ValueError: If prescription not found, no refills remaining,
                        controlled substance, or patient not seen recently
        """
        if prescription_id not in self.db.prescriptions:
            raise ValueError(f"Prescription {prescription_id} not found")

        rx = self.db.prescriptions[prescription_id]

        if rx.controlled_substance:
            raise ValueError(
                "Controlled substance prescriptions cannot be refilled by phone. "
                "The patient must schedule an appointment with their doctor."
            )

        if rx.refills_remaining <= 0:
            raise ValueError(
                "No refills remaining on this prescription. "
                "The patient must see their doctor for a new prescription."
            )

        # Check last visit within 12 months
        patient = self.db.patients[rx.patient_id]
        cutoff = (REFERENCE_DATE - timedelta(days=365)).strftime("%Y-%m-%d")
        recent_visit = any(
            self.db.appointments[aid].status == "completed"
            and self.db.appointments[aid].date >= cutoff
            for aid in patient.appointment_ids
            if aid in self.db.appointments
        )
        if not recent_visit:
            raise ValueError(
                "Prescription refill requires a visit within the last 12 months. "
                "Please schedule a follow-up appointment first."
            )

        rx.refills_remaining -= 1
        return rx

    @is_tool(ToolType.WRITE)
    def request_referral(
        self, patient_id: str, specialty: str, reason: str
    ) -> Referral:
        """
        Request a specialist referral from the patient's primary care doctor.
        Referrals expire after 90 days.

        Args:
            patient_id: The ID of the patient
            specialty: The specialist specialty (dental, dermatology, orthopedics, pediatrics, cardiology)
            reason: Reason for the referral

        Returns:
            The new referral record

        Raises:
            ValueError: If patient not found or has no primary doctor
        """
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")

        patient = self.db.patients[patient_id]
        if not patient.primary_doctor_id:
            raise ValueError(
                "Patient does not have a primary care doctor on file. "
                "Please establish primary care first."
            )

        today = REFERENCE_DATE
        expiry = today + timedelta(days=REFERRAL_EXPIRY_DAYS)

        base_rid = f"ref_{self._patient_last(patient_id)}_{specialty}"
        referral_id = self._make_unique_id(base_rid, self.db.referrals)
        referral = Referral(
            referral_id=referral_id,
            patient_id=patient_id,
            referring_doctor_id=patient.primary_doctor_id,
            specialty=specialty,
            reason=reason,
            status="pending",
            expiry_date=expiry.strftime("%Y-%m-%d"),
        )

        self.db.referrals[referral_id] = referral
        return referral

    @is_tool(ToolType.WRITE)
    def make_payment(
        self, invoice_id: str, amount: float, payment_method_id: str
    ) -> Invoice:
        """
        Process a payment on an invoice.

        Args:
            invoice_id: The ID of the invoice
            amount: The payment amount in dollars
            payment_method_id: The ID of the payment method

        Returns:
            The updated invoice record

        Raises:
            ValueError: If invoice/payment method not found, amount invalid
        """
        if invoice_id not in self.db.invoices:
            raise ValueError(f"Invoice {invoice_id} not found")
        if payment_method_id not in self.db.payment_methods:
            raise ValueError(f"Payment method {payment_method_id} not found")

        inv = self.db.invoices[invoice_id]
        if inv.status == "paid":
            raise ValueError("Invoice is already paid.")

        if amount <= 0:
            raise ValueError("Payment amount must be positive.")
        if amount > inv.patient_responsibility:
            raise ValueError(
                f"Payment amount ${amount:.2f} exceeds patient responsibility "
                f"of ${inv.patient_responsibility:.2f}."
            )

        inv.patient_responsibility -= amount
        patient = self.db.patients[inv.patient_id]
        patient.balance_due = max(0, patient.balance_due - amount)

        if inv.patient_responsibility <= 0:
            inv.status = "paid"
            inv.patient_responsibility = 0.0

        return inv

    @is_tool(ToolType.WRITE)
    def setup_payment_plan(self, invoice_id: str, installments: int) -> Invoice:
        """
        Set up a payment plan for a large invoice. Only for balances over $500,
        maximum 6 installments.

        Args:
            invoice_id: The ID of the invoice
            installments: Number of monthly installments (2-6)

        Returns:
            The updated invoice record

        Raises:
            ValueError: If invoice not found, balance too low, or too many installments
        """
        if invoice_id not in self.db.invoices:
            raise ValueError(f"Invoice {invoice_id} not found")

        inv = self.db.invoices[invoice_id]
        if inv.status == "paid":
            raise ValueError("Invoice is already paid.")

        if inv.patient_responsibility < PAYMENT_PLAN_MIN_BALANCE:
            raise ValueError(
                f"Payment plans are only available for balances over "
                f"${PAYMENT_PLAN_MIN_BALANCE:.2f}. Current balance: "
                f"${inv.patient_responsibility:.2f}."
            )

        if installments < 2 or installments > PAYMENT_PLAN_MAX_INSTALLMENTS:
            raise ValueError(
                f"Installments must be between 2 and {PAYMENT_PLAN_MAX_INSTALLMENTS}."
            )

        inv.status = "payment_plan"
        inv.notes = f"Payment plan: {installments} installments of ${inv.patient_responsibility / installments:.2f}/month"
        return inv

    @is_tool(ToolType.WRITE)
    def update_insurance(
        self,
        patient_id: str,
        provider: str,
        plan_name: str,
        group_number: str,
        member_id: str,
    ) -> Insurance:
        """
        Update or add insurance information for a patient.

        Args:
            patient_id: The ID of the patient
            provider: Insurance provider name
            plan_name: Plan name
            group_number: Group number
            member_id: Member ID

        Returns:
            The new or updated insurance record

        Raises:
            ValueError: If the patient is not found
        """
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")

        patient = self.db.patients[patient_id]

        # If existing insurance, update it
        if patient.insurance_id and patient.insurance_id in self.db.insurance:
            ins = self.db.insurance[patient.insurance_id]
            ins.provider = provider
            ins.plan_name = plan_name
            ins.group_number = group_number
            ins.member_id = member_id
            ins.status = "pending_verification"
            return ins

        # Create new insurance record
        base_iid = f"ins_{self._patient_last(patient_id)}"
        insurance_id = self._make_unique_id(base_iid, self.db.insurance)
        ins = Insurance(
            insurance_id=insurance_id,
            patient_id=patient_id,
            provider=provider,
            plan_name=plan_name,
            group_number=group_number,
            member_id=member_id,
            copay=30.0,
            deductible=1500.0,
            deductible_met=0.0,
            in_network_clinics=[],
            status="pending_verification",
        )
        self.db.insurance[insurance_id] = ins
        patient.insurance_id = insurance_id
        return ins

    @is_tool(ToolType.WRITE)
    def update_patient_info(
        self,
        patient_id: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        emergency_contact: Optional[str] = None,
    ) -> Patient:
        """
        Update a patient's contact information.

        Args:
            patient_id: The ID of the patient
            phone: New phone number (optional)
            address: New address (optional)
            emergency_contact: New emergency contact info (optional)

        Returns:
            The updated patient record

        Raises:
            ValueError: If the patient is not found
        """
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")

        patient = self.db.patients[patient_id]
        if phone is not None:
            patient.phone = phone
        if address is not None:
            patient.address = address
        if emergency_contact is not None:
            patient.emergency_contact = emergency_contact
        return patient

    # ── GENERIC tools ─────────────────────────────────────────────────────

    @is_tool(ToolType.GENERIC)
    def calculate(self, expression: str) -> str:
        """
        Calculate the result of a mathematical expression.

        Args:
            expression: The mathematical expression to calculate, such as '2000 - 350'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

        Returns:
            The result of the mathematical expression.

        Raises:
            ValueError: If the expression is invalid.
        """
        if not all(char in "0123456789+-*/(). " for char in expression):
            raise ValueError("Invalid characters in expression")
        return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))

    @is_tool(ToolType.GENERIC)
    def transfer_to_human_agents(self, summary: str) -> str:
        """
        Transfer the user to a human agent, with a summary of the user's issue.
        Only transfer if
         -  the user explicitly asks for a human agent
         -  the issue requires clinical judgment (medical advice, lab result interpretation, diagnosis discussion)
         -  given the policy and the available tools, you cannot solve the user's issue.

        Args:
            summary: A summary of the user's issue.

        Returns:
            A message indicating the user has been transferred to a human agent.
        """
        return "Transfer successful"

    # ── Assertion helpers (not exposed as tools) ──────────────────────────

    def assert_appointment_status(
        self, appointment_id: str, expected_status: str
    ) -> bool:
        if appointment_id not in self.db.appointments:
            raise ValueError(f"Appointment {appointment_id} not found")
        return self.db.appointments[appointment_id].status == expected_status

    def assert_appointment_exists_for_patient(
        self, patient_id: str, doctor_id: str, date: str | None = None
    ) -> bool:
        today_str = REFERENCE_DATE.strftime("%Y-%m-%d")
        return any(
            a.patient_id == patient_id
            and a.doctor_id == doctor_id
            and (date is None or a.date == date)
            and a.date >= today_str
            and a.status not in ("cancelled", "no_show")
            for a in self.db.appointments.values()
        )

    def assert_prescription_refills(
        self, prescription_id: str, expected_refills: int
    ) -> bool:
        if prescription_id not in self.db.prescriptions:
            raise ValueError(f"Prescription {prescription_id} not found")
        return (
            self.db.prescriptions[prescription_id].refills_remaining == expected_refills
        )

    def assert_referral_exists(self, patient_id: str, specialty: str) -> bool:
        return any(
            r.patient_id == patient_id
            and r.specialty == specialty
            and r.status in ("pending", "scheduled")
            for r in self.db.referrals.values()
        )

    def assert_invoice_status(self, invoice_id: str, expected_status: str) -> bool:
        if invoice_id not in self.db.invoices:
            raise ValueError(f"Invoice {invoice_id} not found")
        return self.db.invoices[invoice_id].status == expected_status

    def assert_patient_balance(self, patient_id: str, max_balance: float) -> bool:
        if patient_id not in self.db.patients:
            raise ValueError(f"Patient {patient_id} not found")
        return self.db.patients[patient_id].balance_due <= max_balance

    def assert_insurance_status(self, insurance_id: str, expected_status: str) -> bool:
        if insurance_id not in self.db.insurance:
            raise ValueError(f"Insurance {insurance_id} not found")
        return self.db.insurance[insurance_id].status == expected_status
