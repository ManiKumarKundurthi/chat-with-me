from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()
password_hash = bcrypt.generate_password_hash('YOUR_PASSWORD').decode('utf-8')
print(password_hash)
