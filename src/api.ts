import axios from 'axios';

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({ baseURL: API_BASE });

// ---------- Types ----------
export type Policy = {
  id: string;
  name: string;
  framework: string;
  status: 'Active' | 'Draft';
  uploaded_at: string;
  controls_count: number;
};

export type Control = {
  id: string;
  policy_id: string;
  target: string;
  metric: string;
  operator: string;
  threshold: string;
  severity: 'High' | 'Medium' | 'Low';
};

export type PolicyDetail = Policy & { controls: Control[] };

export type Scan = {
  id: string;
  policy_id: string;
  policy_name?: string;
  score: number;
  status: 'Compliant' | 'At Risk';
  assets: number;
  run_at: string;
};

export type ScanResult = {
  name: string;
  target: string;
  expected: string;
  actual: string;
  status: 'Passed' | 'Failed' | 'Not Evaluated';
  reason?: string;
};

export type ScanDetail = Scan & { results: ScanResult[] };

export type DashboardSummary = {
  policies: number;
  scans: number;
  passed: number;
  failed: number;
  not_evaluated: number;
  score: number;
};

// ---------- Policies ----------
export const getPolicies = () => api.get<Policy[]>('/api/policies').then(r => r.data);
export const getPolicy = (id: string) => api.get<PolicyDetail>(`/api/policies/${id}`).then(r => r.data);
export const uploadPolicy = (file: File, name?: string, framework = 'Internal') => {
  const form = new FormData();
  form.append('file', file);
  if (name) form.append('name', name);
  form.append('framework', framework);
  return api.post<PolicyDetail>('/api/policies/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const deletePolicy = (id: string) => api.delete(`/api/policies/${id}`);

// ---------- Scans ----------
export const getScans = (startDate?: string, endDate?: string) =>
  api.get<Scan[]>('/api/scans', {
    params: { start_date: startDate, end_date: endDate }
  }).then(r => r.data);
export const runScan = (policyId: string, evidence: any) =>
  api.post<ScanDetail>('/api/scans', { policy_id: policyId, evidence }).then(r => r.data);
export const getScan = (id: string) => api.get<ScanDetail>(`/api/scans/${id}`).then(r => r.data);
export const deleteScan = (id: string) => api.delete(`/api/scans/${id}`);

// ---------- Controls ----------
export const addControl = (policyId: string, control: Partial<Control>) =>
  api.post<Control>(`/api/policies/${policyId}/controls`, control).then(r => r.data);
export const updateControl = (policyId: string, controlId: string, control: Partial<Control>) =>
  api.put<Control>(`/api/policies/${policyId}/controls/${controlId}`, control).then(r => r.data);
export const deleteControl = (policyId: string, controlId: string) =>
  api.delete(`/api/policies/${policyId}/controls/${controlId}`);

// ---------- Dashboard ----------
export const getDashboardSummary = (startDate?: string, endDate?: string) =>
  api.get<DashboardSummary>('/api/dashboard/summary', {
    params: { start_date: startDate, end_date: endDate }
  }).then(r => r.data);
export const resetAllData = () => api.delete('/api/dashboard/reset');
