import axios, {
  AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

import { useAuthStore, type AuthUser } from "@/lib/auth-store";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const api = axios.create({
  baseURL,
  withCredentials: false,
  timeout: 15000,
});

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

/* ---------- request: attach bearer ---------- */
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

/* ---------- response: refresh on 401 once ---------- */
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const { refreshToken, setTokens, clear } = useAuthStore.getState();
  if (!refreshToken) {
    clear();
    return null;
  }
  try {
    const res = await axios.post<{
      access_token: string;
      refresh_token: string;
    }>(`${baseURL}/v1/auth/refresh`, { refresh_token: refreshToken });
    setTokens(res.data.access_token, res.data.refresh_token);
    return res.data.access_token;
  } catch {
    clear();
    return null;
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const original = error.config as RetryConfig | undefined;

    if (status === 401 && original && !original._retry) {
      // Don't try to refresh when the 401 came from the refresh/login endpoint itself
      const url = original.url ?? "";
      if (url.includes("/auth/refresh") || url.includes("/auth/login")) {
        return Promise.reject(error);
      }
      original._retry = true;
      if (refreshPromise === null) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }
      const newToken = await refreshPromise;
      if (newToken) {
        original.headers.set("Authorization", `Bearer ${newToken}`);
        return api.request(original);
      }
    }
    return Promise.reject(error);
  },
);

/* ---------- Auth API ---------- */
export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: string;
};

export async function apiLogin(email: string, password: string): Promise<TokenPair> {
  const res = await api.post<TokenPair>("/v1/auth/login", { email, password });
  return res.data;
}

export async function apiMe(): Promise<AuthUser> {
  const res = await api.get<AuthUser>("/v1/auth/me");
  return res.data;
}

export async function apiLogout(refreshToken: string): Promise<void> {
  await api.post("/v1/auth/logout", { refresh_token: refreshToken });
}

export async function apiRefresh(refreshToken: string): Promise<TokenPair> {
  const res = await axios.post<TokenPair>(`${baseURL}/v1/auth/refresh`, {
    refresh_token: refreshToken,
  });
  return res.data;
}

export async function apiChangePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await api.post("/v1/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

/* ---------- Employees API ---------- */
export type EmployeeOut = {
  id: string;
  email: string;
  name: string;
  role: "admin" | "approver" | "member";
  department_id: string | null;
  hire_date: string | null;
  active: boolean;
};

export async function apiListEmployees(
  config?: AxiosRequestConfig,
): Promise<EmployeeOut[]> {
  const res = await api.get<EmployeeOut[]>("/v1/employees", config);
  return res.data;
}

export type EmployeeCreateInput = {
  email: string;
  password: string;
  name: string;
  role: "admin" | "approver" | "member";
  department_id?: string | null;
  hire_date?: string | null;
};

export type EmployeeUpdateInput = {
  name?: string;
  role?: "admin" | "approver" | "member";
  department_id?: string | null;
  hire_date?: string | null;
  active?: boolean;
  password?: string;
};

export async function apiCreateEmployee(
  input: EmployeeCreateInput,
): Promise<EmployeeOut> {
  const res = await api.post<EmployeeOut>("/v1/employees", input);
  return res.data;
}

export async function apiUpdateEmployee(
  employeeId: string,
  input: EmployeeUpdateInput,
): Promise<EmployeeOut> {
  const res = await api.patch<EmployeeOut>(
    `/v1/employees/${employeeId}`,
    input,
  );
  return res.data;
}

/* ---------- Attendance API ---------- */
export type PunchType = "clock_in" | "clock_out" | "break_start" | "break_end";
export type PunchState = "none" | "working" | "on_break" | "done";
export type DailyStatus =
  | "pending"
  | "normal"
  | "holiday"
  | "leave"
  | "absence"
  | "closed";

export type PunchOut = {
  id: string;
  employee_id: string;
  work_date: string;
  punched_at: string;
  type: PunchType;
  source: string;
};

export type DailyAttendanceOut = {
  id: string;
  employee_id: string;
  work_date: string;
  first_clock_in_at: string | null;
  last_clock_out_at: string | null;
  worked_minutes: number;
  break_minutes: number;
  overtime_minutes: number;
  night_minutes: number;
  status: DailyStatus;
};

export type TodayResponse = {
  work_date: string;
  state: PunchState;
  punches: PunchOut[];
  daily: DailyAttendanceOut | null;
};

export type MonthlyResponse = {
  year: number;
  month: number;
  days: DailyAttendanceOut[];
  stats: {
    working_days: number;
    total_worked_minutes: number;
    total_overtime_minutes: number;
    total_night_minutes: number;
    total_break_minutes: number;
  };
};

export async function apiToday(): Promise<TodayResponse> {
  const res = await api.get<TodayResponse>("/v1/attendance/today");
  return res.data;
}

export async function apiMonthly(
  year: number,
  month: number,
): Promise<MonthlyResponse> {
  const res = await api.get<MonthlyResponse>("/v1/attendance/monthly", {
    params: { year, month },
  });
  return res.data;
}

export async function apiPunch(type: PunchType): Promise<PunchOut> {
  const res = await api.post<PunchOut>("/v1/attendance/punches", { type });
  return res.data;
}

/* ---------- Requests / Approvals ---------- */
export type RequestType =
  | "punch_fix"
  | "overtime_pre"
  | "overtime_post"
  | "leave";
export type RequestStatus =
  | "draft"
  | "pending"
  | "approved"
  | "rejected"
  | "canceled";

export type PunchFixPayload = {
  kind: "punch_fix";
  target_date: string;
  punch_type: PunchType;
  punched_at: string;
  reason: string;
};

export type OvertimePrePayload = {
  kind: "overtime_pre";
  target_date: string;
  planned_minutes: number;
  reason: string;
};

export type OvertimePostPayload = {
  kind: "overtime_post";
  target_date: string;
  actual_minutes: number;
  reason: string;
};

export type LeavePayload = {
  kind: "leave";
  start_date: string;
  end_date: string;
  leave_kind: "full_day" | "half_day_am" | "half_day_pm";
  reason: string;
};

export type RequestPayload =
  | PunchFixPayload
  | OvertimePrePayload
  | OvertimePostPayload
  | LeavePayload;

export type RequestOut = {
  id: string;
  employee_id: string;
  type: RequestType;
  status: RequestStatus;
  target_date: string | null;
  payload: RequestPayload;
  requester_comment: string | null;
  submitted_at: string;
  decided_at: string | null;
};

export type ApprovalOut = {
  id: string;
  request_id: string;
  approver_id: string | null;
  step: number;
  decision: "pending" | "approved" | "rejected";
  decided_at: string | null;
  comment: string | null;
};

export type RequestDetail = RequestOut & { approvals: ApprovalOut[] };

export type ApprovalQueueItem = {
  approval_id: string;
  request: RequestOut;
  step: number;
  requested_by_name: string;
  requested_by_email: string;
};

export async function apiCreateRequest(
  payload: RequestPayload,
  comment?: string | null,
): Promise<RequestDetail> {
  const res = await api.post<RequestDetail>("/v1/requests", { payload, comment });
  return res.data;
}

export async function apiListOwnRequests(): Promise<RequestOut[]> {
  const res = await api.get<RequestOut[]>("/v1/requests");
  return res.data;
}

export async function apiCancelRequest(id: string): Promise<RequestOut> {
  const res = await api.post<RequestOut>(`/v1/requests/${id}/cancel`);
  return res.data;
}

export async function apiApprovalQueue(): Promise<ApprovalQueueItem[]> {
  const res = await api.get<ApprovalQueueItem[]>("/v1/approvals/queue");
  return res.data;
}

export async function apiApprove(
  approvalId: string,
  comment?: string | null,
): Promise<RequestDetail> {
  const res = await api.post<RequestDetail>(
    `/v1/approvals/${approvalId}/approve`,
    { comment },
  );
  return res.data;
}

export async function apiReject(
  approvalId: string,
  comment?: string | null,
): Promise<RequestDetail> {
  const res = await api.post<RequestDetail>(
    `/v1/approvals/${approvalId}/reject`,
    { comment },
  );
  return res.data;
}

/* ---------- Admin: monthly overtime ---------- */
export type OvertimeRowOut = {
  employee_id: string;
  employee_name: string;
  employee_email: string;
  total_overtime_minutes: number;
  total_worked_minutes: number;
  working_days: number;
  alerts_sent: number[];
};

export type OvertimeReport = {
  year: number;
  month: number;
  thresholds_minutes: number[];
  rows: OvertimeRowOut[];
};

export async function apiAdminMonthlyOvertime(
  year: number,
  month: number,
): Promise<OvertimeReport> {
  const res = await api.get<OvertimeReport>("/v1/admin/overtime/monthly", {
    params: { year, month },
  });
  return res.data;
}

/* ---------- Leaves ---------- */
export type LeaveBalanceSummary = {
  employee_id: string;
  employee_name: string;
  employee_email: string;
  year: number;
  leave_type: string;
  granted_days: string; // Decimal as string
  used_days: string;
  carried_over_days: string;
  remaining_days: string;
};

export type LeaveBalanceReport = {
  year: number;
  rows: LeaveBalanceSummary[];
};

export async function apiMyLeaveBalance(
  year?: number,
): Promise<LeaveBalanceSummary> {
  const res = await api.get<LeaveBalanceSummary>("/v1/leaves/balance", {
    params: year ? { year } : undefined,
  });
  return res.data;
}

export async function apiAdminLeaveBalances(
  year: number,
): Promise<LeaveBalanceReport> {
  const res = await api.get<LeaveBalanceReport>("/v1/admin/leaves/balances", {
    params: { year },
  });
  return res.data;
}

export async function apiAdminGrantAllLeaves(
  year: number,
): Promise<{ granted_for_employees: number; year: number }> {
  const res = await api.post("/v1/admin/leaves/grant-all", { year });
  return res.data;
}

export async function apiAdminGrantLeave(input: {
  employee_id: string;
  year: number;
  days: number;
}): Promise<{ employee_id: string; year: number; granted_days: string }> {
  const res = await api.post("/v1/admin/leaves/grant", input);
  return res.data;
}

export async function apiAdminCarryoverLeaves(
  fromYear: number,
): Promise<{ moved: number; from_year: number; to_year: number }> {
  const res = await api.post("/v1/admin/leaves/carryover", {
    from_year: fromYear,
  });
  return res.data;
}

/* ---------- Shifts / Employment Types / Flex ---------- */
export type EmploymentTypeOut = {
  id: string;
  code: string;
  name: string;
  standard_daily_minutes: number;
  standard_weekly_minutes: number;
  core_start: string | null;
  core_end: string | null;
};

export type ShiftOut = {
  id: string;
  employee_id: string;
  work_date: string;
  start_time: string;
  end_time: string;
  break_minutes: number;
};

export type ShiftMonthlyResponse = {
  year: number;
  month: number;
  shifts: ShiftOut[];
};

export type FlexSettlementOut = {
  employee_id: string;
  year: number;
  month: number;
  employment_type_code: string | null;
  required_minutes: number;
  worked_minutes: number;
  surplus_minutes: number;
  core_start: string | null;
  core_end: string | null;
  core_violation_dates: string[];
  working_days: number;
};

export async function apiListEmploymentTypes(): Promise<EmploymentTypeOut[]> {
  const res = await api.get<EmploymentTypeOut[]>("/v1/employment-types");
  return res.data;
}

export async function apiAssignEmploymentType(
  employeeId: string,
  employmentTypeId: string | null,
): Promise<EmploymentTypeOut | null> {
  const res = await api.post<EmploymentTypeOut | null>(
    `/v1/employment-types/assign/${employeeId}`,
    { employment_type_id: employmentTypeId },
  );
  return res.data;
}

export async function apiMonthlyShifts(
  year: number,
  month: number,
  employeeId?: string,
): Promise<ShiftMonthlyResponse> {
  const res = await api.get<ShiftMonthlyResponse>("/v1/shifts/monthly", {
    params: { year, month, ...(employeeId && { employee_id: employeeId }) },
  });
  return res.data;
}

export async function apiUpsertShift(input: {
  employee_id: string;
  work_date: string;
  start_time: string;
  end_time: string;
  break_minutes?: number;
}): Promise<ShiftOut> {
  const res = await api.post<ShiftOut>("/v1/admin/shifts", input);
  return res.data;
}

export async function apiDeleteShift(shiftId: string): Promise<void> {
  await api.delete(`/v1/admin/shifts/${shiftId}`);
}

export async function apiFlexSettlement(
  year?: number,
  month?: number,
  employeeId?: string,
): Promise<FlexSettlementOut> {
  const res = await api.get<FlexSettlementOut>("/v1/shifts/flex", {
    params: {
      ...(year && { year }),
      ...(month && { month }),
      ...(employeeId && { employee_id: employeeId }),
    },
  });
  return res.data;
}

/* ---------- Masters (Departments, Holidays) ---------- */
export type DepartmentOut = {
  id: string;
  name: string;
  code: string | null;
};

export type HolidayOut = {
  id: string;
  date: string;
  name: string;
  type: "national" | "company";
};

export async function apiListDepartments(): Promise<DepartmentOut[]> {
  const res = await api.get<DepartmentOut[]>("/v1/departments");
  return res.data;
}

export async function apiCreateDepartment(
  name: string,
  code?: string | null,
): Promise<DepartmentOut> {
  const res = await api.post<DepartmentOut>("/v1/admin/departments", {
    name,
    code: code ?? null,
  });
  return res.data;
}

export async function apiDeleteDepartment(id: string): Promise<void> {
  await api.delete(`/v1/admin/departments/${id}`);
}

export async function apiListHolidays(year?: number): Promise<HolidayOut[]> {
  const res = await api.get<HolidayOut[]>("/v1/holidays", {
    params: year ? { year } : undefined,
  });
  return res.data;
}

export async function apiCreateHoliday(
  date: string,
  name: string,
  type: "national" | "company" = "national",
): Promise<HolidayOut> {
  const res = await api.post<HolidayOut>("/v1/admin/holidays", {
    date,
    name,
    type,
  });
  return res.data;
}

export async function apiDeleteHoliday(id: string): Promise<void> {
  await api.delete(`/v1/admin/holidays/${id}`);
}

/* ---------- Closings ---------- */
export type ClosingStatusRow = {
  employee_id: string;
  employee_name: string;
  employee_email: string;
  year_month: string;
  closed: boolean;
  closed_at: string | null;
  total_worked_minutes: number;
  total_overtime_minutes: number;
  working_days: number;
};

export type ClosingStatusReport = {
  year: number;
  month: number;
  rows: ClosingStatusRow[];
};

export async function apiClosingStatus(
  year: number,
  month: number,
): Promise<ClosingStatusReport> {
  const res = await api.get<ClosingStatusReport>(
    "/v1/admin/closings/status",
    { params: { year, month } },
  );
  return res.data;
}

export async function apiClosingRecompute(
  year: number,
  month: number,
  employeeId?: string,
): Promise<{ recomputed: number; year_month: string }> {
  const res = await api.post("/v1/admin/closings/recompute", null, {
    params: { year, month, ...(employeeId && { employee_id: employeeId }) },
  });
  return res.data;
}

export async function apiClosingClose(
  year: number,
  month: number,
  employeeId?: string,
): Promise<{ closed: number; year_month: string }> {
  const res = await api.post("/v1/admin/closings/close", null, {
    params: { year, month, ...(employeeId && { employee_id: employeeId }) },
  });
  return res.data;
}

export async function apiClosingReopen(
  year: number,
  month: number,
  employeeId: string,
): Promise<{ ok: boolean }> {
  const res = await api.post("/v1/admin/closings/reopen", null, {
    params: { year, month, employee_id: employeeId },
  });
  return res.data;
}

/* ---------- CSV exports ----------
 *
 * Return RELATIVE paths only. Using `<a href>` directly would send the
 * request without the Authorization header and fail with 401. Always pass
 * these to `downloadCsv` which goes through the authorized axios client.
 */
export function monthlyCsvPath(year: number, month: number): string {
  return `/v1/admin/exports/monthly.csv?year=${year}&month=${month}`;
}

export function leavesCsvPath(year: number): string {
  return `/v1/admin/exports/leaves.csv?year=${year}`;
}

export async function downloadCsv(
  path: string,
  filename: string,
): Promise<void> {
  const res = await api.get(path, { responseType: "blob" });
  const blob = new Blob([res.data], { type: "text/csv;charset=utf-8" });
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(objectUrl);
}
