import pandas as pd
import streamlit as st

from exporters.excel_exporter import create_interface_mapping_excel


st.set_page_config(page_title="Excel Export Preview", page_icon="📄", layout="wide")
st.title("📄 Excel Export Preview")
st.caption("Temporary page for checking the Mapping Specification Excel style only.")


interface_info_df = pd.DataFrame([{
    "생성일 / Creation Date": "2025.01.25",
    "작성자 / Author": "서우형",
    "인터페이스 ID / Interface ID": "OMS_NS_WMS_M_00010",
    "인터페이스 명 / Interface Name": "Zip Receive",
    "인터페이스 패턴 / Interface Pattern": "",
    "스케줄 구동 / Schedule Driven": "",
    "실행 주기 / Execution Cycle": "",
    "최대 레코드(건) / Max Records": "",
    "평균 레코드(건) / Average Records": "",
    "분할 건수 / Split Count": "",
}])

source_transmission_df = pd.DataFrame([{
    "담당자 명 / Contact Name": "",
    "담당자 소속 / Department": "",
    "담당자 연락처 / Contact": "",
    "연계 기술 / Integration Technology": "",
    "Source Svr / Source Server": "nSolution(nOMS)",
    "DB / Database": "nSolution DB",
    "ADAPTER / Adapter": "",
    "조회 패턴 / Query Pattern": "",
}])

target_transmission_df = pd.DataFrame([{
    "담당자 명 / Contact Name": "",
    "담당자 소속 / Department": "",
    "담당자 연락처 / Contact": "",
    "연계 기술 / Integration Technology": "",
    "Target Svr / Target Server": "apac LoIS WMS Work",
    "DB / Database": "IFADM",
    "ADAPTER / Adapter": "",
    "처리 패턴 / Processing Pattern": "Insert Or Update",
}])

source_fields = [
    ("ZIP_CODE", "varchar", "20", "PK", ""),
    ("PLACE_NAME", "nvarchar", "40", "", ""),
    ("COUNTRY_NO", "varchar", "20", "PK", ""),
    ("ADDR1", "nvarchar", "140", "", ""),
    ("ADDR2", "nvarchar", "140", "", ""),
    ("ADDR3", "nvarchar", "140", "", ""),
    ("ADDR4", "nvarchar", "200", "", ""),
    ("LONGITUDE", "numeric", "15", "", ""),
    ("LATITUDE", "numeric", "15", "", ""),
    ("STATUS", "char", "1", "", ""),
    ("REF_01", "nvarchar", "256", "", ""),
    ("REF_02", "nvarchar", "256", "", ""),
    ("REF_03", "nvarchar", "256", "", ""),
    ("IF_STATE", "char", "1", "", "New I/F Column"),
    ("IF_MSG", "varchar", "4000", "", "New I/F Column"),
    ("IF_DATE", "datetime", "NULL", "", "New I/F Column"),
]

mapping_rows = []
for i, (field, typ, size, pk, remark) in enumerate(source_fields, start=1):
    target_field = field if i <= 13 else ""
    mapping_rows.append({
        "송신 시스템 / Source System": "nSolution\n(nOMS)",
        "순번 / Seq.": i,
        "송신 테이블 / Source Table": "LOIS_CO_ZIP",
        "송신 PK / Source PK": pk,
        "송신 필드명 / Source Field": field,
        "송신 타입 / Source Type": typ,
        "송신 사이즈 / Source Size": size,
        "송신 설명 / Source Description": "",
        "송신 비고 / Source Remark": remark,
        "최종 대상 필드 / Final Target Field": target_field,
        "수신 시스템 / Target System": "apac LoIS\nWMS\nManage(Dash)" if i <= 13 else "",
        "수신 테이블 / Target Table": "IFZIP" if i <= 13 else "",
        "수신 PK / Target PK": "",
        "수신 타입 / Target Type": "VARCHAR2" if i <= 13 else "",
        "수신 사이즈 / Target Size": size if i <= 13 else "",
        "수신 설명 / Target Description": "",
        "수신 비고 / Target Remark": "",
    })

mapping_df = pd.DataFrame(mapping_rows)

return_value_df = pd.DataFrame([{
    "송신 시스템 / Source System": "",
    "순번 / Seq.": 1,
    "송신 테이블 / Source Table": "",
    "송신 PK / Source PK": "",
    "송신 필드명 / Source Field": "O_RSLT_CD",
    "송신 타입 / Source Type": "VARCHAR2",
    "송신 사이즈 / Source Size": "10",
    "송신 설명 / Source Description": "작업 성공 구분 코드",
    "송신 비고 / Source Remark": "",
    "수신 시스템 / Target System": "",
    "수신 테이블 / Target Table": "",
    "수신 PK / Target PK": "",
    "수신 필드명 / Target Field": "O_RSLT_CD",
    "수신 타입 / Target Type": "VARCHAR2",
    "수신 사이즈 / Target Size": "10",
    "수신 설명 / Target Description": "작업 성공 구분 코드",
    "수신 비고 / Target Remark": "'S' 성공, 'F' 실패",
}])

excel_bytes = create_interface_mapping_excel(
    interface_info_df=interface_info_df,
    source_transmission_df=source_transmission_df,
    target_transmission_df=target_transmission_df,
    mapping_df=mapping_df,
    return_value_df=return_value_df,
)

st.success("Preview workbook is ready.")

st.download_button(
    label="⬇️ Download Mapping Specification Excel",
    data=excel_bytes,
    file_name="Interface_Mapping_Specification_Preview.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)

st.info(
    "This temporary page uses sample data that resembles the screenshot. "
    "We will connect it to the real app DataFrames after the visual style is confirmed."
)
