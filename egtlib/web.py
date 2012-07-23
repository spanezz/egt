import flask
from flask import request
from .utils import intervals_intersect
import datetime

#app = flask.Flask(__name__, template_folder=os.path.abspath("./templates"))
app = flask.Flask(__name__)


@app.route('/')
def index():
    """
    Main index page
    """
    egt = app.make_egt()
    return flask.render_template("index.html", egt=egt)


@app.route('/stats')
def stats():
    """
    General statistics
    """
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
    """
    Weekly report
    """
    egt = app.make_egt()
    if tags is None:
        rep = egt.weekrpt()
    else:
        rep = egt.weekrpt(tags=frozenset(tags.split("/")))
    return flask.render_template("weekrpt.html", rep=rep)

@app.route('/cal')
def cal():
    """
    Activity calendar
    """
    egt = app.make_egt()
    return flask.render_template("calendar.html", egt=egt)

@app.route('/api/events')
def api_events():
    """
    Return events as JSON
    """
    egt = app.make_egt()

    # Parse date ranges
    since = request.args.get("since", None)
    until = request.args.get("until", None)
    if since is not None: since = datetime.datetime.fromtimestamp(long(since) / 1000.0).date()
    if until is not None: until = datetime.datetime.fromtimestamp(long(until) / 1000.0).date()

    log = []
    count = 0
    for name, p in egt.projects.iteritems():
        for l in p.log:
            if intervals_intersect(l.begin.date(), l.until.date() if l.until else datetime.date.today(), since, until):
                l_until = l.until if l.until is not None else datetime.datetime.utcnow()
                log.append(dict(
                    id=count,
                    title=p.name,
                    allDay=False,
                    start=l.begin.strftime("%s"),
                    end=l_until.strftime("%s"),
                    description=l.body,
                    className="log",
                ))
                count += 1

    return flask.jsonify(log=log, count=count)
