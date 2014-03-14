#!/usr/bin/env python
import datetime
import logging
import optparse
import os

reverse_order = True
deadline = datetime.datetime(2014, 03, 26, 23, 00)

def oracle():
  return float('-inf')
  
def score(e_file, assignment_key, test=False):
  input = [line.strip() for line in e_file.strip().split('\n')]
  answerset = 'test' if test else 'dev'
  answerfile = '%s/eval_data/answers' % (os.path.dirname(os.path.realpath(__file__)),)
  all_answers = [tuple(x.strip().split()) for x in open(answerfile)]
  if len(input) != len(all_answers):
    logging.info('input len = %d, answer len = %d' %(len(input), len(all_answers)))
    return float('-inf'), 100
  (right, wrong) = (0.0,0.0)
  for (i, (sg, sy)) in enumerate(zip(all_answers, input)):
    if sg[0] == answerset:
      (g, y) = (int(sg[1]), int(sy))
      if g == y:
        right += 1
      else:
        wrong += 1
  
  return right / (right + wrong), 100
