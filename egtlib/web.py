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

    def ser_dt(dt):
        if dt is None:
            return None
        return dt.strftime("%s")

    events = []
    count = 0

    # Add logs
    for name, p in egt.projects.iteritems():
        for l in p.log:
            if intervals_intersect(l.begin.date(), l.until.date() if l.until else datetime.date.today(), since, until):
                l_until = l.until if l.until is not None else datetime.datetime.utcnow()
                events.append(dict(
                    id=count,
                    title=p.name,
                    allDay=False,
                    start=ser_dt(l.begin),
                    end=ser_dt(l_until),
                    description=l.body,
                    className="log",
                    color="#689",
                ))
                count += 1

    # Add next-actions with date contexts
    for name, p in egt.projects.iteritems():
        for na in p.next_actions:
            if na.event is None: continue
            d_since = na.event.get("start", None)
            if d_since is not None: d_since = d_since.date()
            d_until = na.event.get("end", None)
            if d_until is not None:
                d_until = d_until.date()
            else:
                d_until = d_since
            if not intervals_intersect(d_since, d_until, since, until): continue
            ev = dict(
                id=count,
                allDay=na.event["allDay"],
                start=ser_dt(na.event["start"]),
                end=ser_dt(na.event["end"]),
                description="\n".join(na.lines),
                className="cal",
            )
            if len(na.lines) > 1:
                ev["title"] = "%s: %s" % (p.name, na.lines[1].strip(" -"))
            else:
                ev["title"] = p.name
            events.append(ev)
            count += 1

    return flask.jsonify(events=events, count=count)
