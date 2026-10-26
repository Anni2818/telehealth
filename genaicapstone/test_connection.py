from db import get_connection


def main():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        try:
            cursor.execute("SELECT DB_NAME();")
            database_name = cursor.fetchone()[0]
            print(f"Connected to database: {database_name}")

            cursor.execute("""
                SELECT
                    d.doctor_id,
                    d.doctor_code,
                    d.display_name,
                    s.specialty_name,
                    d.city
                FROM dbo.doctors AS d
                INNER JOIN dbo.specialties AS s
                    ON s.specialty_id = d.specialty_id
                ORDER BY d.doctor_id;
            """)

            doctors = cursor.fetchall()

            if not doctors:
                print("Connection succeeded, but no doctors were found.")
                return

            print("\nDoctors:")

            for doctor in doctors:
                doctor_id, code, name, specialty, city = doctor
                print(
                    f"{doctor_id} | {code} | {name} | {specialty} | {city}"
                )

        finally:
            cursor.close()

    finally:
        connection.close()


if __name__ == "__main__":
    main()