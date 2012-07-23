import flask


#app = flask.Flask(__name__, template_folder=os.path.abspath("./templates"))
app = flask.Flask(__name__)


@app.route('/')
def index():
    egt = app.make_egt()
    return flask.render_template("index.html", egt=egt)


@app.route('/stats')
def stats():
    egt = app.make_egt()

    blanks = []
    worked = []
    for p in egt.projects.itervalues():
        if p.last_updated is None:
            blanks.append(p)
        else:
            worked.append(p)

    blanks.sort(key=lambda p: p.name)
    worked.sort(key=lambda p: p.last_updated)
    projs = blanks + worked
    return flask.render_template("stats.html", blanks=blanks, worked=worked, projs=projs)


@app.route('/weekrpt')
@app.route('/weekrpt/<path:tags>')
def weekrpt(tags=None):
    egt = app.make_egt()
    if tags is None:
        rep = egt.weekrpt()
    else:
        rep = egt.weekrpt(tags=frozenset(tags.split("/")))
    return flask.render_template("weekrpt.html", rep=rep)

@app.route('/cal')
def cal():
    egt = app.make_egt()
    return flask.render_template("calendar.html", egt=egt)
