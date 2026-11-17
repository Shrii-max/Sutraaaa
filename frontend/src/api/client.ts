/**
 * LexAgent HTTP API Client for Sutra Workspace.
 * 
 * Connects Sutra frontend to the independently runnable LexAgent Legal Research Service
 * over HTTP with JWT authentication, role-based access, grounded statutory research,
 * and precedent intelligence.
 */

export interface HealthResponse {
  status: string;
  environment: string;
  llm_model: string;
  embedding_model: string;
  embedding_dimension: number;
  local_only_mode: boolean;
  telemetry_enabled: boolean;
  disclaimer: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  role: string;
  disclaimer?: string;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: string;
  disclaimer?: string;
}

export interface ResearchCitation {
  source_type: "judgment" | "statute" | "provision";
  id: string;
  title_or_act: string;
  citation_or_section: string;
  verbatim_snippet: string;
  score: number;
  pdf_page?: number;
}

export interface ResearchQueryRequest {
  query: string;
  top_k?: number;
  court_filter?: string;
  act_filter?: string;
}

export interface ResearchQueryResponse {
  query: string;
  answer: string;
  citations: ResearchCitation[];
  is_refusal: boolean;
  refusal_reason?: string | null;
  confidence: number;
  needs_human_review: boolean;
  disclaimer: string;
}

export interface PrecedentItem {
  id: string;
  case_title: string;
  citation: string;
  court: string;
  judgment_date: string;
  ratio_decidendi: string;
  source_url?: string;
  verification_status?: "verified" | "unverified";
}

export interface PrecedentListResponse {
  count: number;
  cases: PrecedentItem[];
  disclaimer: string;
}

// Default base URL points to the running server origin or port 5986
const DEFAULT_BASE_URL =
  import.meta.env?.VITE_LEXAGENT_API_URL ||
  (typeof window !== "undefined" && window.location.origin
    ? window.location.origin
    : "http://localhost:5986");

const TOKEN_STORAGE_KEY = "sutra_lexagent_jwt_token";
const USER_STORAGE_KEY = "sutra_lexagent_user_profile";

class LexAgentClient {
  private baseUrl: string;
  private token: string | null = null;
  private isOnline: boolean | null = null;

  constructor(baseUrl = DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.token = this.loadToken();
  }

  private loadToken(): string | null {
    try {
      return localStorage.getItem(TOKEN_STORAGE_KEY);
    } catch {
      return null;
    }
  }

  private saveToken(token: string | null): void {
    this.token = token;
    try {
      if (token) {
        localStorage.setItem(TOKEN_STORAGE_KEY, token);
      } else {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      }
    } catch {
      // localStorage may fail in restricted sandboxes
    }
  }

  public getToken(): string | null {
    return this.token;
  }

  public setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/+$/, "");
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  /** Build headers including JWT Bearer authorization if authenticated. */
  private getHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...extraHeaders,
    };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return headers;
  }

  /**
   * Check connection and health of the LexAgent HTTP service.
   */
  async checkHealth(): Promise<{ online: boolean; data?: HealthResponse; error?: string }> {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/health`, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(3000),
      });
      if (res.ok) {
        const data = (await res.json()) as HealthResponse;
        this.isOnline = true;
        return { online: true, data };
      }
      this.isOnline = false;
      return { online: false, error: `HTTP ${res.status}: ${res.statusText}` };
    } catch (err) {
      this.isOnline = false;
      return { online: false, error: err instanceof Error ? err.message : String(err) };
    }
  }

  /**
   * Authenticate advocate with email and password to receive JWT.
   */
  async login(email: string, password: string): Promise<TokenResponse> {
    const res = await fetch(`${this.baseUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Login failed with status ${res.status}`);
    }

    const data = (await res.json()) as TokenResponse;
    this.saveToken(data.access_token);
    try {
      localStorage.setItem(
        USER_STORAGE_KEY,
        JSON.stringify({
          id: data.user_id,
          email: data.email,
          role: data.role,
        })
      );
    } catch {
      // Ignore storage errors
    }
    return data;
  }

  /**
   * Register a new advocate or user account.
   */
  async register(
    email: string,
    password: string,
    fullName: string,
    role = "lawyer"
  ): Promise<TokenResponse> {
    const res = await fetch(`${this.baseUrl}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name: fullName, role }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Registration failed with status ${res.status}`);
    }

    const data = (await res.json()) as TokenResponse;
    this.saveToken(data.access_token);
    return data;
  }

  /**
   * Retrieve current authenticated user profile.
   */
  async getCurrentUser(): Promise<UserProfile> {
    const res = await fetch(`${this.baseUrl}/auth/me`, {
      method: "GET",
      headers: this.getHeaders(),
    });

    if (!res.ok) {
      throw new Error(`Failed to fetch user profile: ${res.statusText}`);
    }

    return (await res.json()) as UserProfile;
  }

  /**
   * Log out and clear saved credentials.
   */
  logout(): void {
    this.saveToken(null);
    try {
      localStorage.removeItem(USER_STORAGE_KEY);
    } catch {
      // Ignore
    }
  }

  /**
   * Conduct grounded legal research over local judgments and bare-act statutes.
   */
  async conductResearch(
    params: ResearchQueryRequest
  ): Promise<ResearchQueryResponse> {
    // If no token exists, attempt auto-login with default demo credentials for seamless dev
    if (!this.token) {
      try {
        await this.login("aditi.khanna@sutra.demo", "sutra-demo");
      } catch {
        // Continue and let server return 401 if auth is strictly required
      }
    }

    const res = await fetch(`${this.baseUrl}/research`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        query: params.query,
        top_k: params.top_k ?? 5,
        court_filter: params.court_filter || undefined,
        act_filter: params.act_filter || undefined,
      }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Legal research failed with status ${res.status}`);
    }

    return (await res.json()) as ResearchQueryResponse;
  }

  async ensureAuthenticated(): Promise<string | null> {
    if (this.token) return this.token;
    try {
      const res = await this.login("aditi.khanna@sutra.demo", "sutra-demo");
      return res.access_token;
    } catch {
      return null;
    }
  }

  async getCases(limit = 50): Promise<{ total_cases: number; cases: any[]; disclaimer?: string }> {
    if (!this.token) return { total_cases: 0, cases: [] };
    const res = await fetch(`${this.baseUrl}/api/v1/cases?limit=${limit}`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch cases: ${res.statusText}`);
    }
    return res.json();
  }

  async createCase(data: {
    title: string;
    case_number?: string;
    court?: string;
    dpdp_purpose?: string;
    retention_days?: number;
  }): Promise<any> {
    if (!this.token) throw new Error("Sign in to Sutra before continuing.");
    const res = await fetch(`${this.baseUrl}/api/v1/cases`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to create case: ${res.statusText}`);
    }
    return res.json();
  }

  async getCaseDashboard(caseId: string): Promise<{
    documents_summary: { id: string; filename: string; doc_type: string | null; status: string; language?: string | null }[];
    timeline_events_count: number;
    contradictions_count: number;
    pending_fact_reviews: number;
  }> {
    await this.ensureAuthenticated();
    const response = await fetch(`${this.baseUrl}/api/v1/cases/${encodeURIComponent(caseId)}/dashboard`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) throw new Error("Unable to load case overview");
    return response.json();
  }

  async getDocumentSummary(documentId: string): Promise<{
    summary: string | null;
    needs_human_review?: boolean;
  }> {
    const response = await fetch(`${this.baseUrl}/api/v1/documents/${encodeURIComponent(documentId)}/summary`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) throw new Error("Unable to load document summary");
    return response.json();
  }

  async getCaseTimeline(caseId: string): Promise<any> {
    await this.ensureAuthenticated();
    const res = await fetch(`${this.baseUrl}/api/v1/cases/${encodeURIComponent(caseId)}/timeline`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch timeline: ${res.statusText}`);
    return res.json();
  }

  async getCaseStatements(caseId: string): Promise<any> {
    await this.ensureAuthenticated();
    const res = await fetch(`${this.baseUrl}/api/v1/cases/${encodeURIComponent(caseId)}/statements`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch statements: ${res.statusText}`);
    return res.json();
  }

  async getCaseContradictions(caseId: string): Promise<any> {
    await this.ensureAuthenticated();
    const res = await fetch(`${this.baseUrl}/api/v1/cases/${encodeURIComponent(caseId)}/contradictions`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch contradictions: ${res.statusText}`);
    return res.json();
  }

  async getCaseSimilarCases(caseId: string): Promise<any> {
    await this.ensureAuthenticated();
    const res = await fetch(`${this.baseUrl}/api/v1/cases/${encodeURIComponent(caseId)}/similar-cases`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to fetch similar cases: ${res.statusText}`);
    return res.json();
  }

  async translateDocument(documentId: string, source: string, target: string): Promise<{
    full_translated_text: string;
    needs_human_review: boolean;
    status: string;
    error_message?: string;
    disclaimer: string;
  }> {
    const response = await fetch(`${this.baseUrl}/api/v1/documents/${encodeURIComponent(documentId)}/translate`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ source_language: source, target_language: target }),
    });
    if (!response.ok) throw new Error(`Translation request failed (HTTP ${response.status}).`);
    return response.json();
  }

  async uploadCaseDocument(caseId: string, file: File): Promise<any> {
    if (!this.token) throw new Error("Sign in to Sutra before continuing.");
    const form = new FormData();
    form.append("file", file);
    const headers: Record<string, string> = {};
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const res = await fetch(`${this.baseUrl}/api/v1/cases/${encodeURIComponent(caseId)}/documents`, {
      method: "POST",
      headers,
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Upload failed: ${res.statusText}`);
    }
    return res.json();
  }

  async generateVoiceBrief(caseId: string, depth = "2min"): Promise<any> {
    await this.ensureAuthenticated();
    const res = await fetch(`${this.baseUrl}/api/v1/voice/brief`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ case_id: caseId, depth }),
    });
    if (!res.ok) throw new Error(`Voice brief failed: ${res.statusText}`);
    return res.json();
  }

  /**
   * Play voice brief. Uses browser's native Web Speech API (speechSynthesis)
   * as the primary client-side voice with fallback to server WAV audio.
   */
  playVoiceBrief(script: string, audioBase64?: string | null, language = "en"): void {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(script);
      utterance.lang = language.startsWith("hi") ? "hi-IN" : "en-IN";
      utterance.rate = 0.95;
      window.speechSynthesis.speak(utterance);
      return;
    }
    if (audioBase64) {
      const audio = new Audio(`data:audio/wav;base64,${audioBase64}`);
      audio.play().catch(() => {});
    }
  }

  /**
   * Fetch verified judicial precedents from LexAgent local repository.
   */
  async getPrecedents(limit = 20): Promise<PrecedentListResponse> {
    const res = await fetch(`${this.baseUrl}/api/v1/cases?limit=${limit}`, {
      method: "GET",
      headers: this.getHeaders(),
    });

    if (!res.ok) {
      throw new Error(`Failed to fetch precedents: ${res.statusText}`);
    }

    return (await res.json()) as PrecedentListResponse;
  }
}

export const lexagentClient = new LexAgentClient();
export default lexagentClient;
