import datetime

## Assignment info ##############################################
#
# All four values must be defined

# The assignment's name
name = 'Setup'

# Text used in the leaderboard column header
scoring_method = 'Number'

# Set to true if highest scores are best
reverse_order = True

# The deadline YYYY, MM, DD, HH, MM (24 hour format)
deadline = datetime.datetime(2014, 02, 10, 23, 00)

#################################################################

def oracle():
  return float('-inf')

def score(filedata, assignment_key, test=None):
  """Homework 0 (setup)."""
  value = filedata.split('\n')[0]
  try:
    return (((float(value)-1.0) % 100) + 1, 100)
  except ValueError:
    return (-1, 100)
