import os
import sys
import optparse

def score(a_input, test = False):
    f_data, e_data, a_data = map(open, ['%s/alignment_data/hansards.%s' % (os.path.dirname(os.path.realpath(__file__)), x) for x in ['f','e','a']])

    (size_a, size_s, size_a_and_s, size_a_and_p) = (0.0,0.0,0.0,0.0)
    for (i, (f, e, g, a)) in enumerate(zip(f_data, e_data, a_data, a_input.split('\n'))):
        # dev data is first 37 lines
        if not test and i >= 37:
            break

        # test data is next 447 lines
        if test:
            if i < 37:
                continue
            elif i >= 484:
                break

        fwords = f.strip().split()
        ewords = e.strip().split()
        sure = set([tuple(map(int, x.split("-"))) for x in filter(lambda x: x.find("-") > -1, g.strip().split())])
        possible = set([tuple(map(int, x.split("?"))) for x in filter(lambda x: x.find("?") > -1, g.strip().split())])
        alignment = set([tuple(map(int, x.split("-"))) for x in a.strip().split()])
        size_a += len(alignment)
        size_s += len(sure)
        size_a_and_s += len(alignment & sure)
        size_a_and_p += len(alignment & possible) + len(alignment & sure)
    
    precision = size_a_and_p / size_a
    recall = size_a_and_s / size_s
    aer = 1 - ((size_a_and_s + size_a_and_p) / (size_a + size_s))

    return aer

if __name__ == '__main__':
    optparser = optparse.OptionParser()
    optparser.add_option("-d", "--data", dest="train", default="data/hansards", help="Data filename prefix (default=data)")
    optparser.add_option("-e", "--english", dest="english", default="e", help="Suffix of English filename (default=e)")
    optparser.add_option("-f", "--french", dest="french", default="f", help="Suffix of French filename (default=f)")
    optparser.add_option("-a", "--alignments", dest="alignment", default="a", help="Suffix of gold alignments filename (default=a)")
    optparser.add_option("-t", default=False, help="Test mode", action='store_true')
    (opts, args) = optparser.parse_args()
    f_data = "%s.%s" % (opts.train, opts.french)
    e_data = "%s.%s" % (opts.train, opts.english)
    a_data = "%s.%s" % (opts.train, opts.alignment)

    precision, recall, aer = score(open(f_data), open(e_data), open(a_data), sys.stdin, opts.t)
    sys.stdout.write("Precision = %f\nRecall = %f\nAER = %f\n" % (precision, recall, aer))

    for _ in (sys.stdin): # avoid pipe error
        pass
