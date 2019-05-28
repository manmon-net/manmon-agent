#!/usr/bin/python3

from manmon.mmagent import ManmonAgent
manmonAgent=ManmonAgent()
manmonAgent.load()
time.sleep(10)

logging.basicConfig(filename='/var/lib/manmon/agent.log',level=logging.DEBUG,format='%(asctime)-15s %(levelname)s %(message)s')
logging.info("Initialized agent")

while True:
    try:
        time.sleep(0.01)
        if int(datetime.datetime.utcnow().strftime('%S')) == 0:
            manmonAgent.calc()
            manmonAgent.runDataProcessing()
            time.sleep(1.1)
    except:
        logging.exception("Exception running mmagent")
        time.sleep(10)

