import os
import sys
import time
import math
import urllib
import logging

from collections import defaultdict, namedtuple
import datetime

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2

import scoring.upload_number
import scoring.alignment
import scoring.decode
import scoring.evaluation
import scoring.rerank
import scoring.inflect

#################################################################
# Assignment-related variables
#################################################################

# To enable an assignment:
#
# 1. Uncomment it from the following list
# 2. Edit the file (scoring/NAME.py) and set its deadline

scorer = [
  scoring.upload_number,
#  scoring.alignment,
#  scoring.decode,
#  scoring.evaluation,
#  scoring.rerank,
#  scoring.inflect,
]

# The index of the current assignment (0-indexed)
CURRENT_ASSIGNMENT = len(scorer)-1

# Assignment deadlines in UTC and sore order (True = highest first)
reverse_order = [s.reverse_order for s in scorer]
DEADLINES = [s.deadline for s in scorer]
default_score = [float("-inf") if x else float("inf") for x in reverse_order]

#################################################################
# End 
#################################################################

JINJA_ENVIRONMENT = jinja2.Environment(
  loader=jinja2.FileSystemLoader(
    os.path.join(os.path.dirname(__file__), 'templates')),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)

class Assignment(ndb.Model):
  """A database entry corresponding to an assignment."""
  handle = ndb.KeyProperty()
  number = ndb.IntegerProperty()
  filename = ndb.StringProperty()
  filedata = ndb.BlobProperty()
  score = ndb.FloatProperty()
  test_score = ndb.FloatProperty()
  percent_complete = ndb.IntegerProperty()
  timestamp = ndb.DateTimeProperty(auto_now_add=True)


class Handle(ndb.Model):
  """A database entry recording a user's anonymizing handle."""
  user = ndb.UserProperty() # a handle with no user belongs to the admins
  leaderboard = ndb.BooleanProperty()
  handle = ndb.TextProperty()
  submitted_assignments = ndb.BooleanProperty(repeated=True)


# Clean up old assignments if they never got scored
TIMEOUT_MINUTES = 10
def fail_if_old(assignment, number):
  if assignment.score == default_score[number]:
    earliest_time = datetime.datetime.now() - datetime.timedelta(minutes=TIMEOUT_MINUTES)
    if assignment.timestamp < earliest_time:
      if assignment.percent_complete != 100:
        assignment.percent_complete = 100
        assignment.score = default_score[number]
        assignment.test_score = default_score[number]
        assignment.put()


def get_submission_history(handle, i):
  return Assignment.query(Assignment.handle== handle.key,
                          Assignment.number == i).order(-Assignment.timestamp).fetch()


def most_recent_scored_submission(submission_history, handle, i):
  return next((a for a in submission_history if a.percent_complete == 100 or a.percent_complete is None),
              submission_history[0] if len(submission_history) > 0 else
              Assignment(handle=handle.key, number=i, filedata=None, 
                         score=default_score[i], percent_complete=100))

def update_handle(handle):
  if handle.submitted_assignments is None:
    handle.submitted_assignments = []
  new_assignments = len(scorer) - len(handle.submitted_assignments) 
  if new_assignments > 0:
    handle.submitted_assignments.extend([True] * (new_assignments-1))
    handle.submitted_assignments.append(False)
    handle.put()
  return handle
  
def get_handle(user, request):
  # special case: admin users can request to appear as another handle
  if users.is_current_user_admin():
    req_handle = request.get('as')
    if req_handle:
      logging.info('Admin requested user %s' % req_handle)
      user_handle = ndb.Key(urlsafe=req_handle).get()
      return update_handle(user_handle)
      
  query_result = Handle.query(Handle.user == user).fetch()
  if len(query_result) == 0:
    user_handle = Handle(user = user, 
                         leaderboard = True, 
                         handle = user.nickname())
    user_handle.put()
    return update_handle(user_handle)
  elif len(query_result) == 1:
    return update_handle(query_result[0])
  else:
    logging.warning('More than one handle for user %s' % (user.nickname(),))
    return update_handle(query_result[0])


Message = namedtuple('Message', 'body, type')


class MainPage(webapp2.RequestHandler):
  """Displays the main page."""
  def get(self):
    user = users.get_current_user()
    if user is None:
      return self.redirect(users.create_login_url(self.request.uri))

    messages = []
    user_handle = get_handle(user, self.request)

    if user_handle.user != user:
      body = 'Any changes made on this page will affect handle %s.' % (user_handle.handle,)
      messages.append(Message(body, 'danger'))

    # Retrieve all the user's assignments. For each assignment, choose
    # the most recent submission that is 100% complete. For the most
    # recent assignment, collect its upload history
    assignments = []
    history = []
    progress = [] # ... of the assignment currently uploading
    for i, _ in enumerate(scorer):
      history.append(get_submission_history(user_handle, i))
      for assignment in history[-1]:
        fail_if_old(assignment, i)
      assignments.append(most_recent_scored_submission(history[-1], user_handle, i))
      progress.append(history[-1][0].percent_complete if len(history[-1]) > 0 else 100)

    DEADLINES_PASSED = [datetime.datetime.now() >= x for x in DEADLINES]
    template_values = {
      'user': user.email(),
      'as_handle': user_handle,
      'leaderboard': user_handle.leaderboard,
      'checked': 'checked' if user_handle.leaderboard else '',
      'logout': users.create_logout_url('/'),
      'assignments': assignments,
      'expired': DEADLINES_PASSED,
      'history': history,
      'current': CURRENT_ASSIGNMENT,
      'progress': progress,
      'messages': messages,
      'show_admin_panel': users.is_current_user_admin(),
    }

    template = JINJA_ENVIRONMENT.get_template('index.html')   
    self.response.write(template.render(template_values))


class Progress(webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if user is None:
      self.response.write("0")
      return
    user_handle = get_handle(user, self.request)
    number = int(self.request.get('i'))
    history = get_submission_history(user_handle, number)
    progress = 100
    if len(history) > 0:
      progress = history[0].percent_complete 
    self.response.write(progress)
 

class Submit(webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if user is None:
      return self.redirect(users.create_login_url(self.request.uri))
    user_handle = get_handle(user, self.request)
    user_handle.submitted_assignments[int(self.request.get('number'))] = True
    user_handle.put()
    self.redirect('/?as=%s' % (self.request.get('as'),))


class Upload(webapp2.RequestHandler):
  def post(self):
    user = users.get_current_user()
    if user is None:
      return self.redirect(users.create_login_url(self.request.uri))
    user_handle = get_handle(user, self.request)
    number = int(self.request.get('number'))
    filedata = self.request.get('file')
    assignment = Assignment(handle = user_handle.key,
                            number = number,
                            score = default_score[number],
                            test_score = default_score[number],
                            percent_complete = 0,
                            filedata = filedata,
                            filename = self.request.POST.multi['file'].filename)
    key = assignment.put() # only  way to get a key without fudging one? -- alopez
    (score, percent_complete) = scorer[number].score(filedata, key)
    (test_score, _) = scorer[number].score(filedata, key, test=True)
    assignment.score = score
    assignment.test_score = test_score
    assignment.percent_complete = percent_complete
    assignment.put() 
    self.redirect('/?as=%s' % (self.request.get('as'),))


class QueuedScore(webapp2.RequestHandler):
  def post(self):
    number = int(self.request.get('number'))
    key = ndb.Key(urlsafe=self.request.get('key'))
    data = self.request.get('data')
    scorer[number].queued_score(data, key)
    

## This triggers a potentially large update, so I've disabled it -- alopez
#class Rescore(webapp2.RequestHandler):
#  """Trigger manual rescoring of assignments."""
#  def get(self):
#    user = users.get_current_user()
#    for a in Assignment.query().fetch():
#      if a.filedata:
#        old_score = a.score
#        a.score = scorer[a.number].score(a.filedata)
#        a.test_score = scorer[a.number].score(a.filedata, test=True)
#        a.put()
#    self.redirect('/?')


class ChangeHandle(webapp2.RequestHandler):
  def post(self):
    user = users.get_current_user()
    if user is None:
      return self.redirect(users.create_login_url(self.request.uri))
    user_handle = get_handle(user, self.request)
    user_handle.handle = self.request.get('handle')
    user_handle.leaderboard = (self.request.get('leaderboard') == 'True')
    user_handle.put()
    self.redirect('/?as=%s' % (self.request.get('as'),))


class UpdateSchema(webapp2.RequestHandler):
  '''admin function: update entities created before the schema was extended'''
  def get(self):
    if users.is_current_user_admin():
      count = 0
      for a in Assignment.query().fetch():
        modified = False
        if a.percent_complete is None:
          a.percent_complete = 100
          modified = True
        if a.test_score is None:
          a.test_score = default_score[a.number] # wrong, but expedient
          modified = True
        if a.handle is None:
          query_result = Handle.query(Handle.user == a.user).fetch()
          if len(query_result) == 1:
            a.handle = query_result[0].key
            modified = True
          else:
            logging.warning('Found %d handles for user %s, did not update' % (len(query_result), a.user))
        if modified:
          count += 1
          a.put()
      self.response.write('Updated %d assignments\n' % (count,))
    else:
     self.redirect('/?')


class LeaderBoard(webapp2.RequestHandler):
  def get(self, extension):
    template_values = self.get_template_values()

    if extension == 'html':
      template = JINJA_ENVIRONMENT.get_template('leaderboard.html')
      self.response.write(template.render(template_values))

    else:
      template = JINJA_ENVIRONMENT.get_template('leaderboard.js')
      self.response.write(template.render(template_values))

  def get_template_values(self):
    user = users.get_current_user()
    handles = []
    hidden_users = []
    names = {}
    for handle in Handle.query().fetch():
      # Ignore leaderboard prefs for self and for admins
      if handle.leaderboard:
        handles.append(handle)
      elif user is not None and (handle.user == user or users.is_current_user_admin()):
        handles.append(handle)
        hidden_users.append(handle.handle)
      if users.is_current_user_admin():
        if handle.user:
          names[handle.handle] = handle.user.nickname()
        else:
          names[handle.handle] = 'admin'

    scores = defaultdict(list)
    for handle in handles:
      for i, _ in enumerate(scorer):
        history = get_submission_history(handle, i)
        for assignment in history:
          fail_if_old(assignment, i)
        scores[handle.handle].append(most_recent_scored_submission(history, handle, i).score)

    for i, s in enumerate(scorer):
      scores['oracle'].append(s.oracle() if s.oracle() else default_score[i])
        
    def score_sort(x, y):
      index = CURRENT_ASSIGNMENT
      while index >= 0:
        which = cmp(scores[x][index], scores[y][index])
        if which != 0:
          return which
        index -= 1
      return 0

    sorted_handles = sorted(scores.keys(), cmp=score_sort, reverse=reverse_order[CURRENT_ASSIGNMENT])

    assignments = [{ 'no': i, 'scoring_method': s.scoring_method } for i,s in enumerate(scorer)]

    ranks = {}
    prev_user = ''
    for i,user in enumerate(sorted_handles):
      if not scores.has_key(prev_user) or scores[user][-1] != scores[prev_user][-1]:
        ranks[user] = i + 1
      prev_user = user

    template_values = {
      'assignments': assignments,
      'ranks': ranks,
      'handles': sorted_handles,
      'hidden_users': hidden_users,
      'scores': scores,
      'names': names,
    }

    return template_values

class AdminPanel(webapp2.RequestHandler):
  '''admin function: update entities created before the schema was extended'''
  def get(self):
    if users.is_current_user_admin():
      handles = Handle.query().fetch()
      hw_data = defaultdict(list)
       
      assignments = Assignment.query().order(-Assignment.timestamp).fetch()
      for a in assignments:
        hw_data[a.handle].append(a)
    
      user = users.get_current_user()
      template = JINJA_ENVIRONMENT.get_template('admin.html')
      template_values = {
        'user': user.email(),
        'logout': users.create_logout_url('/'),
        'handles': handles,
        'assignments': hw_data,
      }
      self.response.write(template.render(template_values))
    else:
      self.redirect('/?')


class GetSubmission(webapp2.RequestHandler):
  '''Download a student's submission file'''
  def get(self):
    if users.is_current_user_admin():
      a = ndb.Key(urlsafe=self.request.get('id')).get()
      self.response.write(a.filedata)
    else:
      self.redirect('/?')


application = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/upload', Upload),
  ('/handle', ChangeHandle),
  (r'/leaderboard\.(\w+)', LeaderBoard),
  ('/queued_score', QueuedScore),
  ('/progress', Progress),
  ('/update_schema', UpdateSchema),
  ('/admin', AdminPanel),
  ('/get_submission', GetSubmission),
  ('/submit', Submit),
#  ('/rescore', Rescore),
], debug=True)
