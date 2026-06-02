import sqlite3
import random
import string

DB_PATH = "data/parking.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def register_super_admin(username,email,password):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO super_admins
            (username,email,password)
            VALUES(?,?,?)
            """,
            (
                username,
                email,
                password
            )
        )

        conn.commit()

        return True

    except:

        return False

    finally:

        conn.close()

def login_super_admin(email,password):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM super_admins
        WHERE email=? AND password=?
        """,
        (
            email,
            password
        )
    )

    result = cursor.fetchone()

    conn.close()

    return result is not None

def generate_admin_code(
    super_admin_email,
    zone
):

    conn = get_connection()
    cursor = conn.cursor()

    code = "ADM-" + "".join(
        random.choices(
            string.ascii_uppercase +
            string.digits,
            k=6
        )
    )

    cursor.execute(
        """
        INSERT INTO admin_codes
        (code,super_admin_email,zone)
        VALUES(?,?,?)
        """,
        (
            code,
            super_admin_email,
            zone
        )
    )

    conn.commit()

    conn.close()

    return code

def register_admin(
    username,
    email,
    password,
    code
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT zone
        FROM admin_codes
        WHERE code=?
        """,
        (code,)
    )

    result = cursor.fetchone()

    if not result:

        conn.close()

        return False

    zone = result[0]

    cursor.execute(
        """
        INSERT INTO admins
        (
        username,
        email,
        password,
        zone,
        code
        )
        VALUES
        (
        ?,?,?,?,?
        )
        """,
        (
            username,
            email,
            password,
            zone,
            code
        )
    )

    conn.commit()

    conn.close()

    return True

