from db import get_connection


USER_SELECT = """
    SELECT
        u.user_id,
        u.username,
        u.password_hash,
        u.is_active AS user_active,
        c.customer_id,
        c.customer_code,
        c.is_active AS customer_active
    FROM dbo.app_users AS u
    INNER JOIN dbo.customers AS c
        ON c.customer_id = u.customer_id
"""


def _fetch_user(query, parameters):
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()
        cursor.execute(query, parameters)

        row = cursor.fetchone()

        if row is None:
            connection.commit()
            return None

        columns = [column[0] for column in cursor.description]
        user = dict(zip(columns, row))

        connection.commit()
        return user

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


def find_user_by_username(username):
    return _fetch_user(
        USER_SELECT + " WHERE u.username = ?;",
        (username,),
    )


def find_user_by_id(user_id):
    return _fetch_user(
        USER_SELECT + " WHERE u.user_id = ?;",
        (user_id,),
    )