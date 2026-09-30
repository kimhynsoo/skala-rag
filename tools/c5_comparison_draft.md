# C5 경쟁제품 비교표 초안

기준일: 2026-09-30

공개 자료에서 제품군이 겹치는 후보와 제원을 정리했다. 목표 기업 쪽의 동등 조건 사양과 RAG/D 분석이 없으므로 이 표는 **후보 비교**이며 우위·열위 판정은 유보한다.

## 복수 후보가 확인된 제품군

| 대상 기업·제품 | 후보 제품 | 후보 제품의 공개 사양 | 현재 비교 가능한 결론 |
|---|---|---|---|
| 디에스 주식회사 — 어드밴스드 반도체 후공정 불량 검출 | [KLA eDR7380 / Micro-SR 첨단 패키징 검사](https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging)<br>[Onto Innovation Dragonfly G3 첨단 패키징 검사](https://investors.ontoinnovation.com/news/news-details/2024/Onto-Innovation-Debuts-Sub-surface-Defect-Inspection-for-Advanced-Packaging/default.aspx) | eDR7380: 첨단 웨이퍼 레벨 패키징용 e-beam 결함 검토·분류. Micro-SR: 로직·메모리·복합반도체 및 첨단 패키징 광학 결함 검토.<br>HBM 고객의 적층 다이·웨이퍼 위치 계측 적용; 개선형 subsurface defect detection 발표. | HBM 패키징 검사 후보가 2개 확인됨. 비전·e-beam 방식과 검사 조건 차이로 성능 비교는 보류. |
| 망고부스트코리아 주식회사 — Data Processing Unit | [NVIDIA BlueField-3 DPU](https://www.nvidia.com/en-us/networking/products/data-processing-unit)<br>[AMD Pensando DPU](https://www.amd.com/en/products/data-processing-units/pensando.html) | 최대 400 Gb/s 연결; SDN, 스토리지, 사이버보안의 line-rate 처리.<br>AMD 제품 페이지는 DPU가 AMD 자체 시험에서 평균 117 MPPS를 수행한다고 기술. 시험 조건이 타사 수치와 같지 않아 수치 간 직접 비교 금지. | DPU 후보 2개. NVIDIA의 링크 속도와 AMD의 packet 처리량은 지표/시험 조건이 달라 직접 비교 불가. |
| (주)아나배틱세미 — BMS용 반도체칩 개발 및 솔루션 제공 | [Texas Instruments BQ79600-Q1](https://www.ti.com/product/BQ79600-Q1)<br>[Analog Devices LTC6813-1](https://www.analog.com/en/products/ltc6813-1.html) | MCU와 TI 배터리 모니터 IC 간 통신 브리지; BMS, HEV/EV, 연료전지, 에너지 저장 용도.<br>최대 18개 직렬 배터리 셀 측정; 총 측정 오차 2.2mV 미만. | BMS 칩 후보 2개지만 통신 브리지와 셀 모니터링은 기능 블록이 다름. |
| 엑시나 주식회사 — CXL 기반 Large Scale Data 가속기 개발 | [Astera Labs Leo CXL Smart Memory Controllers](https://www.asteralabs.com/products/leo-smart-memory-controllers)<br>[XConn Technologies Apollo CXL 2.0 / PCIe Gen 5 switch](https://www.prnewswire.com/news-releases/xconn-technologies-launches-the-industrys-first-and-only-hybrid-cxl-2-0-and-pcie-gen-5-switch-301895313.html) | 제품 브리프 기준 DDR5 채널 최대 5600 MT/s, 메모리 확장 구성 최대 2 TB.<br>회사 발표에 따르면 하이브리드 CXL 2.0 및 PCIe Gen 5 스위치로 메모리 풀링·확장을 지원. | Astera는 메모리 컨트롤러, XConn은 스위치로 CXL 시스템의 서로 다른 계층을 담당. |
| 주식회사 더유엠에스 — 초소형 레이다 모션 감지 센서 | [Infineon BGT60TR13C](https://www.infineon.com/part/BGT60TR13C)<br>[Acconeer A121 60 GHz Pulsed Coherent Radar](https://acconeer.com/products) | 제조사 60 GHz 레이다 센서 제품군; 제품 상태 Active.<br>제조사 제품 페이지는 60 GHz PCR, 최대 20m 범위, 통합 RF 프런트엔드·안테나 패키지를 제시. | 60GHz 레이다 후보 2개. 공개 거리/안테나/환경 조건이 통일되지 않아 직접 비교 불가. |
| 디노티시아 — Seahorse, Mnemos | [Hailo Hailo-8 edge AI processor](https://hailo.ai/products/ai-accelerators/hailo-8-ai-accelerator)<br>[DEEPX DX-M1 AI Accelerator](https://deepx.ai/products/dx-m1) | 최대 26 TOPS; 온칩 메모리 통합을 제조사가 표방.<br>25 TOPS (INT8), PCIe Gen3 x4, 4GB LPDDR5 (5600 MT/s), 소비전력 1W 최소~5W 최대. | AI accelerator 후보 2개. Hailo 최대 26 TOPS, DEEPX 25 TOPS(INT8); Hailo의 동일 정밀도·전력 조건이 확인되지 않아 우열 보류. |
| 주식회사 디퍼아이 — AI 반도체 칩 및 반도체 모듈 | [Hailo Hailo-8 edge AI processor](https://hailo.ai/products/ai-accelerators/hailo-8-ai-accelerator)<br>[DEEPX DX-M1 AI Accelerator](https://deepx.ai/products/dx-m1) | 최대 26 TOPS; 온칩 메모리 통합을 제조사가 표방.<br>25 TOPS (INT8), PCIe Gen3 x4, 4GB LPDDR5 (5600 MT/s), 소비전력 1W 최소~5W 최대. | AI accelerator 후보 2개. Hailo와 DEEPX의 목표 칩 및 워크로드별 벤치마크가 필요. |
| (주)에이와이이노베이티브 — AI 기반 차량 보안 반도체 | [NXP S32G Vehicle Network Processors](https://www.nxp.com/products/processors-and-microcontrollers/s32-automotive-platform/s32g-vehicle-network-processors:S32G-PROCESSORS)<br>[Infineon AURIX Security Solutions](https://www.infineon.com/product-information/aurix-security-solutions) | 차량 네트워크용 멀티코어 Arm Cortex-A53 SoC; 제품군은 lockstep MCU 옵션 등을 제공.<br>AURIX 32-bit MCU 제품군은 자동차 애플리케이션용 embedded Hardware Security Module (HSM)을 제공. | 자동차 보안·네트워크용 인접 제품 후보 2개. 목표기업 보안칩과 기능 범위 차이 확인 필요. |
| (주)와이젯 — 60GHz 무선 영상 전송 | [Peraso X130 / X720 60GHz chipsets](https://perasoinc.com/chipset_products)<br>[Qualcomm QCA64x8 / QCA64x1 60 GHz WiGig chipsets](https://spectrum.ieee.org/qualcomm-introduces-new-chipsets-for-60-ghz-wifi) | 다중 기가비트 IEEE 802.11ad MAC/PHY baseband 및 용도별 RFIC 조합.<br>보도 자료는 60GHz Wi-Fi 칩셋군을 소개; 제3자 기사에서 10+ Gbps를 언급하나 세대·시험조건은 원문 데이터시트로 재확인 필요. | 60GHz 무선 칩 후보 2개. WiGig/802.11ad 규격은 겹치지만 링크 조건·영상 전송 성능 자료가 부족. |
| 하이퍼비주얼에이아이 — 인공지능 프로세서 | [Hailo Hailo-8 edge AI processor](https://hailo.ai/products/ai-accelerators/hailo-8-ai-accelerator)<br>[DEEPX DX-M1 AI Accelerator](https://deepx.ai/products/dx-m1) | 최대 26 TOPS; 온칩 메모리 통합을 제조사가 표방.<br>25 TOPS (INT8), PCIe Gen3 x4, 4GB LPDDR5 (5600 MT/s), 소비전력 1W 최소~5W 최대. | AI 프로세서 후보 2개. Hailo 최대 26 TOPS와 DEEPX 25 TOPS(INT8)는 조건 확인 전 직접 순위화하지 않음. |

## 단일 후보 또는 인접 제품만 확인

| 대상 기업·제품 | 후보 제품 | 확인된 공개 사양 | 제한 |
|---|---|---|---|
| 블루닷 주식회사 — 동영상 처리 반도체 IP와 소프트웨어 | [VeriSilicon Hantro VC9000D](https://www.verisilicon.com/en/IPPortfolio/HantroVC9000D) | 8K 디코딩; AV1, HEVC, H.264, AVS2, VP9, JPEG 지원. | 비디오 처리 IP 제품군 후보. 대상 코덱 및 IP 구성별로 확인 필요. 블루닷 제품의 공개 모델 및 코덱별 성능이 없어 정량 비교 불가. |
| 주식회사 에프에스2 — 2차원소재 기반 3차원 반도체 | [CDimension 초박막 2D 반도체 소재](https://www.cdimension.com/blog/from-lab-curiosity-to-industry-ready-how-cdimension-is-making-2d-materials-work-for-the-future-of-electronics) | 기업 발표는 초박막 2D 반도체 소재의 상용 판매 개시를 설명하며 상세 전기적 사양은 제시하지 않음. | 동일 소재 분야 참고 후보. FS2의 단결정 2D 및 M3D 통합기술과 직접 경쟁하는지는 미확인. 제품 성능과 독립적인 비교 사양이 부족함. |
| 주식회사 터넬 — T-SRAM TritCellTM, AI SoC UniBrainTM | [Synopsys DesignWare SRAM Memory Compilers](https://www.synopsys.com/designware-ip/memories-logic-libraries/sram-memory-compilers.html) | 임베디드 SRAM 단일/듀얼 포트 및 멀티포트 메모리 컴파일러 포트폴리오. | 일반 SRAM IP 참고제품. 삼진법 T-SRAM과 구조가 다를 수 있어 직접 경쟁으로 단정하지 않음. 삼진법 SRAM과 동일 구조 제품의 공개 사양을 확인하지 못함. |
| 가산기술 — 이미지 인식용 On-sensor AI Chip | [Sony Semiconductor Solutions IMX500 Intelligent Vision Sensor](https://www.sony.com/en/SonyInfo/News/Press/202005/20-037E) | 약 12.3MP 이미지 센서에 AI 처리 기능 통합. | 온센서 추론 통합 제품 형태 기준 후보. 동일 워크로드 추론 성능 자료는 미확인. 가산기술 칩의 센서 사양·모델·추론 벤치마크가 필요함. |
| 뉴로리얼리티비전 — 이벤트 카메라 | [Sony Semiconductor Solutions / Prophesee IMX636 event-based sensor](https://www.prophesee.ai/event-based-sensor-imx636-sony-prophesee) | 1280×720; 픽셀 지연 <100μs(1000 lux), <1000μs(5 lux); 동적범위 >86dB (5 lux–100 klux). | 이벤트 센서의 비교 후보. Sony와 Prophesee의 공동 제품으로 표기. 목표 기업 제품의 해상도·지연·감도 조건이 없어 정량 우열 비교 불가. |
| 주식회사 아크칩스 — Analog/Mixed-Signal/RF 반도체 IP | [Synopsys DesignWare Mixed-Signal IP](https://news.synopsys.com/home?item=122691) | 혼합신호 IP 포트폴리오 및 인터페이스 셀 라이브러리 제품 발표. | IP 포트폴리오 참고 후보. 개별 IP 블록과 공정 노드가 맞는지 추가 확인 필요. 제품별 면적·전력·공정 노드의 동등 사양을 확보하지 못함. |
| (주)유엑스팩토리 — 온센서 AI NPU, End-Device AI | [Sony Semiconductor Solutions IMX500 Intelligent Vision Sensor](https://www.aitrios.sony-semicon.com/edge-ai-devices/imx500) | 4056×3040(약 12.3MP) 이미지 센서에 AI 처리 기능 통합; 프레임 속도는 출력 모드별로 구분. | 온센서 AI 구조 비교 후보. 센서 내장형과 별도 NPU/end-device 구성을 구분해야 함. UX Factory의 TOPS, 전력, 공정, 지원 모델 자료가 없어 성능 비교 불가. |

## 후보 지정 보류

| 기업 | 사유 |
|---|---|
| 아이디어스투실리콘 주식회사 (C07) | 기업 레코드의 메인아이템이 비어 있어 검색 범위를 설정하지 못함. |
| 엘스페스 주식회사 (C11) | 검색에서 제조사 공식 실리콘 커패시터 비교제품 사양을 확보하지 못함. |
| 관악아날로그(주) (C20) | 메인아이템이 제품군을 특정하지 않아 책임 있는 경쟁제품 검색이 어려움. |

## C5 마무리에 필요한 자료

- D의 대상 기업별 `technology_analysis.성능지표`와 시험·검증 조건
- B의 RAG 인덱스 및 관련 업계 기준 근거
- 후보 기업·제품별 데이터시트에서 동일 조건으로 측정한 지표
- 위 자료가 겹치는 지표에 한해서 우위·열위를 판단
