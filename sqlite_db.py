import sqlite3

conn = sqlite3.connect('proxy.db')
curs = conn.cursor()

curs.execute('CREATE TABLE IF NOT EXISTS Proxy (ip, port, type, code, country)')

with open('steroids.txt') as f:
    while True:
        line = f.readline()
        if not line: break

        line = line.rstrip()
        line = line.split(',')
        tmp = ' '.join(line[4:])

        line = line[:4]
        line.append(tmp)

        line = map(lambda x: "'" + x + "'", line)
        vals = ','.join(line)

        print vals

        curs.execute('INSERT INTO PROXY VALUES (%s)' % vals)
        conn.commit()
conn.close()
