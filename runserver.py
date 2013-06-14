from navi import app
import os
port = int(os.environ.get('PORT', 5000))
debug = os.environ['DEBUG']
app.run(port = port, debug = debug)