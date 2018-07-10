import shelve
from sys import argv


def main():
    filename = argv[1]
    dataserv = argv[2:]
    print dataserv
    for i in range(0, len(dataserv), 2):
        s = shelve.open('dataserver' + dataserv[i])
        print '~~~before deleting at dataserver' + dataserv[i] + ': '
        print s
        if str(0) + filename in s:
            del s[str(0) + filename]
        print '~~~after deleting at dataserver' + dataserv[i] + ': '
        print s
        s.close()


if __name__ == "__main__":
    if len(argv) < 3:
        print('usage: %s <path> <dataport1> <dataport2> ..' % argv[0])
        exit(1)
    main()
