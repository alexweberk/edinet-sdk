# Define the structure of the output dictionary for document processors
# This structured_data is what will be passed to the LLM tools
from collections.abc import Hashable
from typing import Any

StructuredDocData = dict[str, Any]

Record = dict[Hashable, Any]
# {
#     "要素ID": "jppfs_cor:SalariesAndAllowancesSGA",
#     "項目名": "給料及び手当、販売費及び一般管理費",
#     "コンテキストID": "CurrentYTDDuration",
#     "相対年度": "当四半期累計期間",
#     "連結・個別": "連結",
#     "期間・時点": "期間",
#     "ユニットID": "JPY",
#     "単位": "円",
#     "値": "1044176000",
# }

CsvFileAsRecords = list[Record]
FilenameRecords = dict[str, CsvFileAsRecords]
