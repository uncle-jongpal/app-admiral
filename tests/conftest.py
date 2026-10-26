import os
import tempfile

# 시험이 진짜 기록(logs\admiral-날짜.log)에 섞이지 않게, admiral 을 import 하기 전에 기록 폴더를 임시로 돌린다
os.environ["ADMIRAL_LOG_DIR"] = tempfile.mkdtemp(prefix="admiral-test-logs-")
