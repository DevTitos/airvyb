from py_vapid import Vapid
from cryptography.hazmat.primitives import serialization

vapid = Vapid()
vapid.generate_keys()

private_key = vapid.private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

public_key = vapid.public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

print("Private Key:\n")
print(private_key.decode())

print("\nPublic Key:\n")
print(public_key.decode())