# MLV Lab 홈페이지 운영 안내

홈페이지는 **Notion의 내용과 GitHub의 디자인·이미지 백업**으로 관리합니다. 기존 Google Sites를 수정하거나 유지할 필요 없이 GitHub Pages가 HTML과 이미지를 제공합니다.

- 사이트: [mlvlab.github.io](https://mlvlab.github.io/)
- 저장소: [mlvlab/mlvlab.github.io](https://github.com/mlvlab/mlvlab.github.io)
- Notion: [MLV Lab homepage DB](https://app.notion.com/p/MLV-Lab-homepage-DB-3cf341ce261380569133f0248ce2c8af)

```text
Notion DB → fetch_notion.py → build/ 데이터 + site/img/ 이미지
          → render.py → validate_site.py → GitHub Pages
```

## 평소에는 이렇게 관리합니다

1. Notion의 해당 DB에서 내용을 수정합니다. 논문은 Publications, 소식은 News, 멤버는 People입니다.
2. 새 이미지와 교체 이미지는 `Photo File`, `Thumbnail File`, `Image File`에 **파일을 직접 업로드**합니다.
3. GitHub Actions의 **Build site from Notion and deploy → Run workflow**를 실행하면 바로 새 빌드를 요청할 수 있습니다. 자동 빌드는 6시간 간격으로 예약되어 있으며 실제 시작·완료 시각은 GitHub 상황에 따라 늦어질 수 있습니다.
4. Actions 실행이 성공했는지와 실제 홈페이지에서 수정 내용이 보이는지 확인합니다.

`Show on Site` 체크를 끄면 행을 삭제하지 않고 숨길 수 있습니다. 페이지 본문에만 글을 적어서는 대부분의 DB에 반영되지 않으므로 아래의 **열 이름**을 사용해 주세요. 열 이름과 Site Content의 `Key`는 코드가 그대로 읽으므로 임의로 바꾸지 않습니다.

레이아웃, 메뉴, 고정 안내 문구는 `template.html`에서 관리합니다. `main`에 변경을 올리면 자동 빌드가 시작됩니다. 도메인 설정은 콘텐츠 관리와 별도이며 이 저장소의 이미지 보존·백업 작업에서 변경하지 않습니다.

## 논문과 썸네일 추가

Publications에 새 행을 만들고 다음 항목을 입력합니다.

| 열 | 입력할 내용 |
|---|---|
| `Title` | 논문 제목 |
| `Year` | 발표 연도, 숫자 |
| `Type` | `Conference`, `Journal`, `Workshop`, `Preprint`, `Thesis`, `Book chapter` 등 기존 분류 |
| `Authors` | 저자를 쉼표로 구분한 문자열 |
| `Venue`, `Venue (short)` | 학회·저널 전체 이름과 짧은 이름 |
| `Paper Link` | 논문 URL |
| `Thumbnail File` | 홈페이지 목록에 표시할 대표 그림 파일 |
| `MLV Members` | 저자에 해당하는 People 행과 관계 연결 |
| `Research Topics` | 해당 연구 주제와 관계 연결 |
| `Code`, `Video`, `Slides`, `Poster`, `Project Page`, `Demo`, `Supplement` | 필요한 추가 링크 |
| `Presentation`, `Collaboration`, `Note` | Oral 등 발표 정보, 협력기관, 추가 설명 |
| `Order`, `Show on Site` | 순서와 표시 여부 |

- **최신 연도부터** 표시합니다. 같은 연도는 **Order가 빈 논문 먼저 → Order가 작은 논문부터**이며, 동일한 조건에서는 최근 생성한 행이 먼저입니다. 새 논문을 해당 연도 맨 위에 넣으려면 `Year`를 입력하고 `Order`를 비워 두면 됩니다.
- 썸네일은 `Thumbnail File`에 한 장을 직접 올리는 방법이 가장 간단합니다. 기존 Figures 이미지와의 연결이나 `Thumbnail` / `Thumbnail URL`도 읽지만 외부 URL의 접근 권한·만료에 영향을 받습니다.
- `MLV Members`를 연결해야 멤버별 논문 조회에 포함됩니다. 저자 이름에 버튼이 붙으려면 `Authors`의 이름도 People의 영문 이름과 맞아야 합니다.
- Research 페이지의 **Representative papers**에는 Topics DB의 `Related Publications` 관계로 추가합니다. Publications의 `Research Topics`만 설정하는 것은 주제 필터 연결입니다.
- `Presentation`에 Gold Star, Spotlight, Oral, Highlight가 있으면 해당 배지가 표시됩니다. 별도의 `Highlight` 체크박스는 현재 화면에서 사용하지 않습니다.

## 다른 DB의 주요 필드

| DB | 주요 열과 운영 방법 |
|---|---|
| People | `Name`, `Korean Name`, `Group`, `Status`, `Position`, `Email`, `Tel`, `Google Scholar`, `Homepage`, `CV`, `Research Interests`, `Photo File`. 졸업생은 `Graduated`, `After Graduation`도 사용 |
| News | `News title`, `Date`, 선택적으로 `Link 1`–`Link 3`, `Link Label 1`–`Link Label 3`. 날짜가 최신인 소식부터 표시하고 같은 날짜는 Order가 큰 순서 |
| Topics | `Topic`, `Description`, `Related Publications` |
| Figures | `Caption`, `Image File`, `Topic`, 선택적으로 `Publication`. Topic·Publication 관계는 각각 첫 번째 항목만 사용 |
| Teaching | `Semester`, `Year`, `Term`, `Course`, `Code`, `Note`, `Institution`. 연도 내림차순, 같은 해는 Fall 먼저, 다음 Course 이름순 |
| Photos | `Caption`, `Image File` |
| Highlights | `Caption`, `Image File`. 모든 행을 숨기면 홈에서 이 영역만 생략. `Link` 열은 현재 슬라이드에서 사용하지 않음 |
| MLV TV | `Title`, `YouTube ID`, `YouTube URL`. 표준 watch/youtu.be URL을 쓰거나 11자리 ID를 입력 |
| Site Content | `Key`, `Value`, 일부 행의 페이지 본문. 아래 표 참고 |

People·Topics·Figures·Photos·Highlights·MLV TV는 **Order가 작은 순서**이며 빈 값은 0으로 취급합니다. Notion 화면에서 행을 드래그한 순서가 곧 홈페이지 순서는 아닙니다.

People의 현재 멤버는 `Status = Current`를 사용합니다. `Group`은 기존 값인 `Faculty`, `Post-doctoral researcher`, `Ph.D. Student`, `Master Student`, `Undergraduate Student`, `Intern`, `Doctoral Alumni`, `Master's Alumni`를 유지해 주세요. 임의의 새 그룹 이름은 현재 템플릿에 표시되지 않을 수 있습니다. 교수 소개는 첫 번째 `Faculty` 행의 본문에서 Heading 2인 **About Me**, **Awards** 아래 내용을 읽습니다.

## Site Content에서 바꿀 수 있는 내용

각 행의 `Key`는 아래 값을 유지하고 `Value`를 수정합니다.

| Key | 역할 |
|---|---|
| `lab_name`, `lab_short_name` | 연구실 전체 이름·짧은 이름. 홈 제목, 상단 이름, footer 등에 반영 |
| `pi_email`, `apply_email`, `google_scholar` | 연락처·지원 이메일·Scholar 링크 |
| `home_intro` | 홈 소개 본문 |
| `contact_address_en`, `contact_address_ko` | 영문·국문 주소. 영문 주소 첫 줄은 Contact 상단, 첫 두 줄은 footer에도 표시 |
| `contact_map_embed_url`, `contact_map_link` | 지도 임베드 주소와 지도 열기 링크 |
| `contact_calendar_embed_url` | 달력 임베드 주소 |
| `openings_title`, `openings_en`, `openings_ko` | 모집 제목·영문·국문 본문 |
| `openings_open` | 문자열 `true`이면 모집 중, `false`이면 Closed. 모집 페이지 자체는 유지 |
| `home_news_count` | 홈에 처음 표시할 뉴스 개수, 기본 10 |
| `home_new_count` | 최신 뉴스에 NEW를 붙일 개수, 기본 5. **0이면 배지 숨김** |
| `youtube_url`, `facebook_url`, `x_url` | SNS 링크 |
| `youtube_icon_url`, `facebook_icon_url`, `x_icon_url` | SNS 아이콘 이미지 주소 |
| `home_hero_image_url`, `home_collaborators_image_url` | 홈 대표 이미지·협력기관 이미지 주소 |
| `research_banner_url`, `logo_url`, `banner_people_url`, `banner_photos_url` | 연구 배너·로고·People/Photos 배너 주소 |
| `youtube_channel_id`, `youtube_auto_sync` | 자동 수집할 채널 ID와 사용 여부. 문자열 `false`로 자동 수집 중지 |

`home_intro`, `contact_address_en`, `contact_address_ko`, `openings_en`, `openings_ko`는 **행의 페이지 본문이 있으면 본문을 우선**합니다. 그 밖의 행도 Value가 `(`로 시작하면 본문을 읽습니다. 본문을 사용하는 행에서 Value만 바꾸고 결과가 그대로라면 페이지 안쪽 내용을 확인하세요.

- 뉴스의 `New` 체크박스는 사용하지 않습니다. 날짜순 최신 `home_new_count`개에 자동으로 배지가 붙습니다. 개수에는 0 이상의 정수를 입력해 주세요.
- 본문은 문단, 굵게, 링크, 기본 목록 위주로 작성합니다. 중첩 블록, 표, 토글, 본문 이미지, 콜아웃은 홈페이지로 자동 복제되지 않으며 제목·인용문의 Notion 디자인도 그대로 보존되지 않습니다.
- Site Content의 이미지 Key는 **Value에 이미지 URL을 넣는 방식**입니다. 별도의 파일 첨부 열을 자동으로 읽지는 않습니다. 이 이미지의 원본도 영구 보관하고 snapshot을 갱신해 주세요.
- MLV TV는 채널 RSS의 최근 최대 15개 영상 중 DB에 없는 영상을 목록 위에 자동 추가합니다. 특정 자동 영상을 숨기려면 해당 URL/ID를 DB에 추가하고 `Show on Site`를 끕니다.

## Google Sites와 이미지 보존

새 사이트는 빌드 때 이미지를 다운로드해 `site/img/`에서 직접 제공합니다. 방문자가 Notion의 임시 이미지 주소나 기존 Google Sites에서 그림을 불러오지 않습니다.

이미지 원본은 **Notion File → 외부 URL → 저장소 snapshot** 순서로 사용합니다. Google Sites의 `googleusercontent.com/sitesv/…` 주소는 만료되거나 외부에서 접근할 수 없어 건너뜁니다. 새 이미지·교체 이미지는 해당 DB의 `… File`에 직접 업로드하고, 기존 URL만 남아 있는 중요 이미지도 파일로 옮겨 주세요.

`snapshot/`은 삭제하지 않습니다. 데이터와 이미지의 복사본이며, 행의 고유 ID를 우선하고 기존 공개본에는 이름·논문 제목·사진 설명으로 대체 이미지를 연결합니다. 기존 공개본에는 Notion ID가 없으므로 설명이 같은 여러 사진은 원래 순서에 의존합니다. 이런 사진을 재정렬하거나 설명을 바꿀 때는 `Image File`도 함께 등록하는 것이 정확합니다. 갱신 시 이전 이미지는 `manifest.json`의 `archive`에 보존하므로 숨겼다가 다시 표시할 때도 복구할 수 있습니다. 모든 신규 이미지가 자동으로 저장소에 커밋되는 것은 아니므로 아래 갱신 절차를 사용합니다.

기존 Google Sites를 삭제하더라도 별도로 연결한 Google Drive의 논문·CV, Google Calendar, YouTube 등의 파일·공개 권한은 각각 유지해야 해당 링크가 계속 작동합니다.

## 백업과 복구

### 자동 백업과 배포 검사

Actions는 생성한 사이트를 `validate_site.py`로 검사하고, **site-backup**이라는 다운로드 가능한 artifact를 **90일** 보관하도록 요청합니다. 실제 보관 기간은 GitHub 조직·저장소 정책의 제한을 받을 수 있습니다. 장기 보관할 실행의 백업은 만료 전에 내려받으세요.

**Notion 조회가 실패하면 오래된 데이터로 자동 대체해 배포하지 않습니다.** 실패 원인을 수정하고 빌드를 다시 실행합니다. 마지막으로 성공한 사이트를 새 배포로 덮어쓰지 않도록 하는 동작이며, `snapshot/`은 필요할 때 선택하는 수동 복구 수단입니다.

### 저장소 snapshot 갱신

현재 서비스 중인 사이트에서 데이터와 이미지를 가져오려면:

```bash
python refresh_snapshot.py --from-site https://mlvlab.github.io/
```

공개 사이트에는 Notion 고유 ID가 포함되지 않습니다. 이미 ID가 보관된 snapshot은 이 명령으로 덮어쓰지 못하게 보호하며, 그 경우 아래 `--from-build` 방식을 사용합니다.

새 Notion 데이터로 만든 로컬 빌드에서 가져오려면:

```bash
python fetch_notion.py
python render.py
python validate_site.py
python refresh_snapshot.py --from-build
```

갱신 결과를 검토한 뒤 `snapshot/` 변경 사항을 Git에 저장합니다. 공개 사이트의 이전 배포를 백업하는 것과 Notion의 최신 변경 내용을 백업하는 것은 다릅니다. 후자는 새 빌드가 성공한 뒤 갱신해야 합니다. Notion 자체의 내보내기도 함께 보관하면 원본 편집 내용을 복구하는 데 도움이 됩니다.

### Notion 없이 수동 복구·미리 보기

```bash
pip install -r requirements.txt
python validate_site.py --snapshot
python render.py --snapshot
open site/index.html
```

이 명령은 **저장소 snapshot 시점**의 사이트를 로컬에 생성합니다. 자동으로 원격 사이트에 배포하거나 최신 Notion을 복구하지 않습니다. 복구가 필요한 경우 결과를 확인한 뒤 별도로 배포해야 합니다.

`python validate_site.py`는 일반 빌드의 `build/site_data.json`, `build/assets.json`, `site/img/`를 검사합니다. `--snapshot`은 저장소의 snapshot 데이터·manifest·이미지 파일을 검사합니다.

화면 동작을 수정했다면 Node.js 22 이상에서 `node --test tests/test_frontend.cjs`로 빈 Highlights, 뉴스 전체 보기, NEW 배지 등의 회귀 검사를 실행할 수 있습니다.

## 연결 설정과 문제 확인

- Notion integration은 해당 상위 페이지와 10개 데이터 소스에 읽기 권한이 있어야 합니다. 페이지의 Connections에서 연결 상태를 확인합니다.
- GitHub의 **Settings → Secrets and variables → Actions**에 `NOTION_TOKEN`을 저장합니다. 토큰은 저장소 파일에 넣지 않습니다.
- GitHub Pages의 Source는 **GitHub Actions**입니다.
- **DB를 다른 워크스페이스로 옮겼을 때** (예: 개인 계정 → 연구실 계정): `config.json`의 `parent_page`에 옮겨진 "MLV Lab homepage DB" 페이지 링크(또는 ID)를 넣으면, 빌더가 그 아래의 10개 DB를 **제목(People, Publications, Research Topics, Research Figures, News, Teaching, Photos, MLV TV, Home Highlights, Site Content)으로 찾아** 씁니다. 아래 `data_sources` ID는 제목을 못 찾았을 때의 예비값이므로 DB 제목은 바꾸지 마세요. 새 워크스페이스에서 만든 integration을 그 페이지의 Connections에 추가하고 `NOTION_TOKEN`을 새 토큰으로 바꾸는 것까지 해야 합니다.
- 수정이 반영되지 않으면 최신 Actions 결과 → `Show on Site` → 열 이름/Key → 실제 본문/Value 우선순위 순으로 확인합니다.
- 이미지가 없으면 `… File` 업로드, 파일 접근 가능 여부, 빌드의 이미지 경고·검사 결과를 확인합니다.

## 주요 파일

| 파일 | 역할 |
|---|---|
| `config.json` | `parent_page`(DB들이 있는 상위 페이지), 예비 데이터 소스 ID, 이미지 크기, 기본 YouTube 채널 |
| `fetch_notion.py` | Notion 데이터·이미지 읽기, snapshot 대체 이미지 연결 |
| `render.py` | 데이터와 template으로 사이트 생성, `--snapshot` 수동 복구 |
| `template.html` | 화면 디자인·메뉴·표시 기능 |
| `validate_site.py` | 생성 사이트·이미지의 배포 전 검사 |
| `refresh_snapshot.py` | 공개 사이트 또는 로컬 빌드로 snapshot 갱신 |
| `snapshot/` | 저장소에 보관하는 데이터·이미지 백업 |
| `.github/workflows/deploy.yml` | 6시간 간격/수동/main 변경 빌드, 검사, 백업, Pages 배포 |

`build/`와 `site/`는 생성 결과로 Git에서 제외합니다. 자동 실행은 snapshot 변경을 저장소에 자동 커밋하지 않습니다.
