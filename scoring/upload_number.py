import datetime

# Assignment info
reverse_order = True
deadline = datetime.datetime(2014, 02, 10, 23, 00)

def oracle():
  return float('-inf')

def score(filedata, assignment_key, test=None):
  """Homework 0 (setup)."""
  value = filedata.split('\n')[0]
  try:
    return (((float(value)-1.0) % 100) + 1, 100)
  except ValueError:
    return (-1, 100)
