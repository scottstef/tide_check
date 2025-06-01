import base64
import os

flask_secret = os.urandom(24)
flask_secret = base64.b64encode(flask_secret).decode('utf-8')
print(flask_secret)
