from flask import Flask, request

from widgets.map_widget import MapWidget

app = Flask(__name__)


@app.route('/api/map')
def generate_map():
    widget = MapWidget(**request.args)
    return widget.render()
