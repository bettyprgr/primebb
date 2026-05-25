import socket
import threading
import subprocess
import time
import re

active = {}


def pipe(src, dst):
  try:
      while True:
          data = src.recv(65536)
          if not data:
              break
          dst.sendall(data)
  except:
      pass
  finally:
      try:
          src.close()
      except:
          pass
      try:
          dst.close()
      except:
          pass


def start_proxy(port):
  srv = socket.socket()
  srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  try:
      srv.bind(('0.0.0.0', port))
  except:
      return
  srv.listen(10)
  print(f"[proxy] 0.0.0.0:{port} -> 127.0.0.1:{port}")

  def accept_loop():
      while True:
          try:
              cli, _ = srv.accept()
              tgt = socket.socket()
              tgt.connect(('127.0.0.1', port))
              threading.Thread(target=pipe, args=(cli, tgt), daemon=True).start()
              threading.Thread(target=pipe, args=(tgt, cli), daemon=True).start()
          except:
              pass

  threading.Thread(target=accept_loop, daemon=True).start()


while True:
  out = subprocess.check_output('netstat -ano', shell=True).decode(errors='ignore')
  for m in re.finditer(r'127\.0\.0\.1:(\d{4,5})\s+\S+\s+LISTENING', out):
      port = int(m.group(1))
      if port not in active:
          active[port] = True
          start_proxy(port)
  time.sleep(2)
