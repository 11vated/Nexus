<<<<<<< SEARCH
=======
from flask import Flask, json

app = Flask(__name__)

@app.route('/hello')
def say_hello():
    return json jsonify({'message': 'Hello, World!'})

@app.route('/goodbye')
def say_goodbye():
    return json jsonify({'message': 'Goodbye, World!'})

if __name__ == '__main__':
    app.run(port=5000)
>>>>>>> REPLACE
