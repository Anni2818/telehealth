import json

from app.services.appointment_service import list_available_slots


def main():
    specialty = input("Specialty, for example Dermatology: ").strip()
    city = input("City, for example Pune: ").strip()
    requested_date = input("Appointment date (YYYY-MM-DD): ").strip()

    try:
        slots = list_available_slots(
            specialty=specialty,
            city=city,
            requested_date=requested_date,
        )
    except ValueError as error:
        print(f"Invalid input: {error}")
        return

    if not slots:
        print("No available slots matched your search.")
        return

    print(f"\nAvailable slots: {len(slots)}")
    print(json.dumps(slots, indent=2))


if __name__ == "__main__":
    main()