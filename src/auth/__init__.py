import bcrypt


def hash_password(password: str):
    """ Convert password into a hashed password """
    password_bytes = password.encode('utf-8')
    hashed_bytes = bcrypt.hashpw(password=password_bytes, salt=bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    # Convert both input and stored hash back to bytes for comparison
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))