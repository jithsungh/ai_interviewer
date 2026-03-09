# Frontend–Backend Integration Analysis Report

## 1. UI Data Requirements

### CandidateDashboard
| Field | Type | Source |
|---|---|---|
| `currentUser.name` | `string` | `candidateMockData.currentUser` |
| `candidatePerformanceStats.totalInterviews` | `number` | `candidateMockData.candidatePerformanceStats` |
| `candidatePerformanceStats.averageScore` | `number` | |
| `candidatePerformanceStats.passRate` | `number` | |
| `candidatePerformanceStats.totalPracticeTime` | `string` (e.g. `"18h 30m"`) | |
| `candidatePerformanceStats.scoreHistory[]` | `{ date, score }` | |
| `candidatePerformanceStats.skillBreakdown[]` | `{ skill, score }` | |
| `candidatePerformanceStats.strongAreas[]` | `string[]` | derived |
| `candidatePerformanceStats.improvementAreas[]` | `string[]` | derived |
| `submissionWindows[]` (upcoming) | `InterviewSubmissionWindow` | `candidateMockData.submissionWindows` |
| `pastSubmissions[]` | `InterviewSubmission` | `candidateMockData.pastSubmissions` |

### Interviews Page
| Field | Type |
|---|---|
| `submissionWindows[].id` | `number` |
| `submissionWindows[].name` | `string` |
| `submissionWindows[].scope` | `string` |
| `submissionWindows[].start_time` | `string` |
| `submissionWindows[].end_time` | `string` |
| `submissionWindows[].organization.name` | `string` |
| `submissionWindows[].role_templates[].role.name` | `string` |
| `submissionWindows[].role_templates[].template.total_estimated_time_minutes` | `number` |
| `submissionWindows[].max_allowed_submissions` | `number` |
| `submissionWindows[].allow_resubmission` | `boolean` |
| `pastSubmissions[].final_score` | `number` |
| `pastSubmissions[].role.name` | `string` |
| `pastSubmissions[].status` | `string` |
| `pastSubmissions[].window.organization.name` | `string` |
| `pastSubmissions[].submitted_at` | `string` |
| `pastSubmissions[].result.result_status` | `string` |

### InterviewWindowDetail
| Field | Type |
|---|---|
| `window.name` | `string` |
| `window.organization.name` | `string` |
| `window.scope` | `string` |
| `window.max_allowed_submissions` | `number` |
| `window.allow_resubmission` | `boolean` |
| `window.role_templates[].role.name` | `string` |
| `window.role_templates[].template.total_estimated_time_minutes` | `number` |

### Profile Page
| Field | Type |
|---|---|
| `currentUser.name` | `string` |
| `currentUser.email` | `string` |
| `currentCandidate.profile_metadata.phone` | `string` |
| `currentCandidate.profile_metadata.experience_years` | `number` |
| `currentCandidate.profile_metadata.cgpa` | `number` |
| `currentCandidate.profile_metadata.skills[]` | `string[]` |
| `currentCandidate.profile_metadata.bio` | `string` |
| `currentCandidate.profile_metadata.location` | `string` |
| `currentCandidate.profile_metadata.linkedin_url` | `string` |
| `currentCandidate.profile_metadata.github_url` | `string` |
| `currentCandidate.profile_metadata.portfolio_url` | `string` |
| `currentCandidate.profile_metadata.education[]` | `Education[]` |
| `currentCandidate.profile_metadata.work_experience[]` | `WorkExperience[]` |
| `resumes[]` | `Resume[]` |

### SubmissionReport Page
| Field | Type |
|---|---|
| `submission.role.name` | `string` |
| `submission.window.organization.name` | `string` |
| `submission.window.name` | `string` |
| `submission.submitted_at` | `string` |
| `submission.result.normalized_score` | `number` |
| `submission.result.result_status` | `string` |
| `submission.result.recommendation` | `string` |
| `submission.result.section_scores` | `Record<string, number>` |
| `submission.result.strengths` | `string` |
| `submission.result.weaknesses` | `string` |
| `submission.exchanges[].question_text` | `string` |
| `submission.exchanges[].difficulty_at_time` | `string` |
| `submission.exchanges[].evaluation.total_score` | `number` |

### Practice Page
| Field | Type |
|---|---|
| `practiceSkills[].id` | `string` |
| `practiceSkills[].name` | `string` |
| `practiceSkills[].icon` | `string` |
| `practiceSkills[].questionCount` | `number` |
| `practiceSkills[].completedCount` | `number` |
| `practiceSkills[].color` | `string` |
| `practiceQuestions[].id` | `string` |
| `practiceQuestions[].skill` | `string` |
| `practiceQuestions[].question` | `string` |
| `practiceQuestions[].difficulty` | `string` |
| `practiceQuestions[].estimatedTime` | `number` |
| `practiceQuestions[].completed` | `boolean` |

### InterviewSession / InterviewLobby (old mock data)
| Field | Type |
|---|---|
| `interviewTemplates[].id` | `string` |
| `interviewTemplates[].name` | `string` |
| `interviewTemplates[].type` | `InterviewType` |
| `interviewTemplates[].description` | `string` |
| `interviewTemplates[].duration` | `number` (minutes) |
| `interviewTemplates[].questionCount` | `number` |
| `interviewTemplates[].topics[]` | `string[]` |
| `interviewQuestions` | `Question[]` (open-ended + coding) |

---

## 2. API Coverage

### Endpoints That Already Support the UI

| UI Feature | API Endpoint | Status |
|---|---|---|
| Auth / Login | `POST /auth/login` | ✅ Full |
| Auth / Me | `GET /auth/me` | ✅ Full |
| Auth / Register | `POST /auth/register/candidate` | ✅ Full |
| Auth / Logout | `POST /auth/logout` | ✅ Full |
| Auth / Refresh | `POST /auth/refresh` | ✅ Full |
| Candidate Profile | `GET /candidate/profile` | ✅ Full |
| Candidate Profile Update | `PUT /candidate/profile` | ✅ Full |
| Candidate Stats | `GET /candidate/stats` | ✅ Full |
| Candidate Windows | `GET /candidate/windows` | ✅ Partial (see gaps) |
| Candidate Submissions | `GET /candidate/submissions` | ✅ Partial (see gaps) |
| Interview Exchanges | `GET /interviews/{id}/exchanges` | ✅ Full |
| Interview Progress | `GET /interviews/{id}/progress` | ✅ Full |
| Interview Results | `GET /evaluations/results/{id}` | ✅ Full |
| Interview Reports | `GET /evaluations/results/{id}/reports` | ✅ Full |
| Practice Questions | `GET /candidate/practice/questions` | ✅ Full |
| Practice Start | `POST /candidate/practice/start` | ✅ Full |
| Code Submit | `POST /coding/submit` | ✅ Full |
| Session Start | `POST /interviews/sessions/start` | ✅ Full |
| Session Complete | `POST /interviews/sessions/complete` | ✅ Full |
| Proctoring Events | `POST /proctoring/events` | ✅ Full |
| Audio Session | `POST /audio/ingestion/.../start` | ✅ Full |

---

## 3. Missing Backend Support

### 3.1 Missing Endpoints

| UI Requirement | Expected Endpoint | Status |
|---|---|---|
| Resume upload / list | `GET /candidate/resumes`, `POST /candidate/resumes` | ❌ **Not in API** |
| Resume AI analysis (parsed_data, match_score, feedback) | `GET /candidate/resumes/{id}/analysis` | ❌ **Not in API** |
| Legacy Dashboard (mockData.ts: upcomingInterviews, performanceStats) | N/A | ⚠️ Replaced by candidate stats |

### 3.2 Missing Fields

| API Endpoint | UI Expected Field | API Field | Gap |
|---|---|---|---|
| `GET /candidate/stats` | `totalPracticeTime` (string like `"18h 30m"`) | `total_practice_time_minutes` (int) | ⚠️ **Structural** — UI formats string from int (adapter handles this) |
| `GET /candidate/stats` | `strongAreas[]` | Not returned | ⚠️ **Missing** — derived in adapter from `skill_breakdown` |
| `GET /candidate/stats` | `improvementAreas[]` | Not returned | ⚠️ **Missing** — derived in adapter from `skill_breakdown` |
| `GET /candidate/windows` | `role_templates[].template.name` | Not returned | ❌ **Missing** — API returns flat `role` + `duration_minutes`, no template detail |
| `GET /candidate/windows` | `role_templates[].template.description` | Not returned | ❌ **Missing** |
| `GET /candidate/windows` | `timezone` | Not returned | ❌ **Missing** — API `CandidateWindowDTO` has no timezone field |
| `GET /candidate/windows` | `organization_type` | Not returned | ❌ **Missing** — only `organization.{id, name}` is returned |
| `GET /candidate/submissions` | `template` (full template object) | Not returned | ❌ **Missing** — API returns flat DTO |
| `GET /candidate/submissions` | `exchanges[]` (full audit trail) | Not returned in list | ⚠️ **Separate call** — use `GET /interviews/{id}/exchanges` |
| `GET /candidate/submissions` | `result.section_scores` | Not in list DTO | ⚠️ **Separate call** — use `GET /evaluations/results/{id}` |
| `GET /candidate/submissions` | `result.strengths / weaknesses` | Not in list DTO | ⚠️ **Separate call** |
| `GET /candidate/profile` | `resumes[]` | Not returned | ❌ **Missing** — no resume endpoint in API |
| `GET /candidate/practice/questions` | `practiceSkills[].icon` | Not returned | ⚠️ **UI-only** — mapped from skill ID in adapter |
| `GET /candidate/practice/questions` | `practiceSkills[].color` | Not returned | ⚠️ **UI-only** — mapped from skill ID in adapter |
| `GET /candidate/practice/questions` | `practiceQuestions[].estimatedTime` | Not returned | ⚠️ **Missing** — hardcoded default in adapter |

### 3.3 Structural Mismatches

#### Windows: Flat vs Nested

**UI expects:**
```ts
InterviewSubmissionWindow {
  organization: Organization          // full org
  role_templates: [{
    role: Role                        // full role
    template: InterviewTemplate       // full template with name, description
  }]
}
```

**API returns:**
```ts
CandidateWindowDTO {
  organization: { id, name }          // flat DTO
  role: { id, name }                  // single flat role (not array)
  duration_minutes: number            // proxy for template time
  // NO template name/description
}
```

**Resolution:** Adapter fills template defaults; template name/description unavailable.

#### Submissions: Flat vs Nested Result

**UI expects:**
```ts
InterviewSubmission {
  role: Role                          // nested
  window: InterviewSubmissionWindow   // nested with organization
  result: InterviewResult             // nested
  exchanges: InterviewExchange[]      // nested
}
```

**API returns:**
```ts
CandidateSubmissionDTO {
  role: { id, name }                  // flat
  window: { id, name }               // flat
  organization: { id, name }         // flat
  result_status: string               // top-level
  recommendation: string              // top-level
  // NO exchanges, NO section_scores, NO strengths/weaknesses
}
```

**Resolution:** Adapter reconstructs nesting. Exchanges and detailed results require separate API calls.

#### Stats: Practice Time Format

**UI expects:** `totalPracticeTime: "18h 30m"` (string)  
**API returns:** `total_practice_time_minutes: 1110` (integer)  
**Resolution:** Adapter converts minutes to formatted string.

#### Stats: Derived Areas

**UI expects:** `strongAreas: string[]`, `improvementAreas: string[]`  
**API returns:** only `skill_breakdown: [{ skill, score }]`  
**Resolution:** Adapter derives strong/weak from skill breakdown using threshold (≥75 = strong).

---

## 4. Proposed API Contract Changes

### 4.1 Resume Endpoints (New)

```
GET /api/v1/candidate/resumes

Response:
{
  data: [{
    id: number,
    file_url: string,
    parsed_text: string | null,
    extracted_data: {
      name: string,
      email: string,
      skills: string[],
      experience_years: number,
      education: object[],
      work_experience: object[],
      certifications: string[],
      summary: string,
      match_score: number,
      feedback: [{
        category: string,
        score: number,
        feedback: string,
        suggestions: string[]
      }]
    },
    uploaded_at: string,
    created_at: string
  }],
  pagination: PaginationMeta
}

POST /api/v1/candidate/resumes
Content-Type: multipart/form-data
Body: { file: File }
Response: 201 { id, file_url, uploaded_at }
```

### 4.2 Enrich CandidateWindowDTO

Add the following fields to `CandidateWindowDTO`:

```jsonc
{
  // existing fields...
  "timezone": "string",               // window timezone
  "template_name": "string | null",   // denormalized template name
  "template_description": "string | null"
}
```

### 4.3 Enrich CandidateSubmissionDTO

Add the following fields to `CandidateSubmissionDTO`:

```jsonc
{
  // existing fields...
  "template_name": "string | null"    // denormalized template name
}
```

### 4.4 Add estimated_time to PracticeQuestionDTO

```jsonc
{
  // existing fields...
  "estimated_time_minutes": "number"  // per-question time estimate
}
```

---

## 5. Dual-Data Architecture (Current vs Legacy)

The project has **two parallel data systems**:

| Layer | File | Used By |
|---|---|---|
| **Legacy mock** | `src/data/mockData.ts` | Dashboard, InterviewLobby, InterviewReport, InterviewTypesSection |
| **Candidate mock** | `src/data/candidateMockData.ts` | Candidate Dashboard, Interviews, Profile, Practice, Reports, Settings |
| **Interview questions** | `src/data/interviewQuestions.ts` | InterviewSession |

The **legacy mock** uses `src/types/interview.ts` types (string IDs, flat structures).  
The **candidate mock** uses `src/types/database.ts` types (numeric IDs, relational structures).  

The API aligns with `database.ts` types. The legacy `interview.ts`/`mockData.ts` is for the interview session flow and is not yet covered by API integration.

---

## 6. Implemented Adapter Functions

| Adapter Function | Input (API) | Output (UI) |
|---|---|---|
| `mapCurrentUser` | `CurrentUserResponse` | `User` |
| `mapCandidateProfile` | `APICandidateProfileResponse` | `{ user: User, candidate: Candidate }` |
| `mapCandidateStats` | `APICandidateStatsResponse` | `CandidatePerformanceStatsUI` |
| `mapCandidateWindow` | `APICandidateWindowDTO` | `InterviewSubmissionWindow` |
| `mapCandidateWindows` | `APICandidateWindowDTO[]` | `InterviewSubmissionWindow[]` |
| `mapCandidateSubmission` | `APICandidateSubmissionDTO` | `InterviewSubmission` |
| `mapCandidateSubmissions` | `APICandidateSubmissionDTO[]` | `InterviewSubmission[]` |
| `mapInterviewResult` | `APIInterviewResultResponse` | `InterviewResult` |
| `mapExchangeItem` | `APIExchangeItemDTO` | `InterviewExchange` |
| `mapExchangeItems` | `APIExchangeItemDTO[]` | `InterviewExchange[]` |
| `mapPracticeSkill` | `APIPracticeSkillDTO` | `PracticeSkillUI` |
| `mapPracticeQuestion` | `APIPracticeQuestionDTO` | `PracticeQuestionUI` |

---

## 7. File Structure Created

```
src/
  types/
    api.ts                  ← API response types (from openapi.json)
    database.ts             ← UI model types (existing, unchanged)
    interview.ts            ← Legacy UI types (existing, unchanged)
  adapters/
    candidateAdapters.ts    ← API → UI model mappers
  services/
    apiClient.ts            ← Thin HTTP client with auth headers
    authService.ts          ← Login, logout, token management
    candidateService.ts     ← Candidate API calls with mock fallback
  data/
    candidateMockData.ts    ← Mock data (existing, unchanged)
    mockData.ts             ← Legacy mock data (existing, unchanged)
    interviewQuestions.ts   ← Interview questions (existing, unchanged)
```

### Usage

```ts
// Enable API mode via environment variable:
// VITE_USE_API=true
// VITE_API_BASE_URL=https://api.example.com/api/v1

// In components, import from services instead of data:
import { getCandidateStats, getCandidateWindows } from '@/services/candidateService';

// Falls back to mock data automatically when API is unavailable
const stats = await getCandidateStats();
const { data: windows } = await getCandidateWindows();
```
