const JSON_HEADERS = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      ...JSON_HEADERS,
      ...(options.headers || {}),
    },
    ...options,
  });

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const raw = payload && typeof payload === "object" ? (payload.detail ?? payload.error) : null;
    let message;
    if (Array.isArray(raw)) {
      message = raw.map((e) => (typeof e === "object" ? (e.msg || JSON.stringify(e)) : String(e))).join("; ");
    } else if (raw != null) {
      message = String(raw);
    } else {
      message = response.statusText || "Request failed";
    }
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export const api = {
  health: () => request("/api/health", { headers: { Accept: "application/json" } }),

  // --- Live ops ---
  getDashboard: () => request("/api/live/dashboard"),
  runCollectorOnce: () => request("/api/live/collector/run-once", { method: "POST" }),
  listMappingReview: () => request("/api/live/mapping-review?limit=100"),
  resolveMappingReview: (mappingDecisionId, payload) =>
    request(`/api/live/mapping-review/${mappingDecisionId}/resolve`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listRuns: (params = {}) => {
    const search = new URLSearchParams();
    if (params.limit) search.set("limit", String(params.limit));
    if (params.sourceId) search.set("source_id", String(params.sourceId));
    if (params.channelId) search.set("channel_id", String(params.channelId));
    if (params.activeOnly) search.set("active_only", "true");
    const suffix = search.size ? `?${search.toString()}` : "";
    return request(`/api/live/runs${suffix}`);
  },
  getRunDetail: (runId) => request(`/api/live/runs/${runId}`),
  getRunProvenance: (runId) => request(`/api/live/runs/${runId}/provenance`),
  getRunMetrics: (runId) => request(`/api/metrics/runs/${runId}`),

  // --- Ontology (read) ---
  listElectrodeBatches: () => request("/api/ontology/electrode-batches"),
  getBatchByName: (batchName) =>
    request(`/api/ontology/electrode-batches/by-name/${encodeURIComponent(batchName)}`),
  getBatchLineage: (batchId) =>
    request(`/api/ontology/electrode-batches/${batchId}/lineage`),
  getBatchDescendants: (batchId) =>
    request(`/api/ontology/electrode-batches/${batchId}/descendants`),
  listMaterials: () => request("/api/ontology/materials"),
  getMaterial: (id) => request(`/api/ontology/materials/${id}`),
  listMaterialLots: () => request("/api/ontology/material-lots"),
  listCellBuilds: () => request("/api/ontology/cell-builds"),
  getCellBuild: (id) => request(`/api/ontology/cell-builds/${id}`),
  getCellBuildLineage: (id) => request(`/api/ontology/cell-builds/${id}/lineage`),
  listEquipmentAssets: () => request("/api/ontology/equipment-assets"),
  listProtocolVersions: () => request("/api/ontology/protocol-versions"),
  listProcessRuns: () => request("/api/ontology/process-runs"),
  listOperators: () => request("/api/ontology/operators"),
  listFixtures: () => request("/api/ontology/fixtures"),

  // --- Ontology (search/summary) ---
  getOntologySummary: () => request("/api/ontology/summary"),
  searchOntology: (q, entityTypes, limit) => {
    const params = new URLSearchParams({ q });
    if (entityTypes) params.set("entity_types", entityTypes);
    if (limit) params.set("limit", String(limit));
    return request(`/api/ontology/search?${params.toString()}`);
  },

  // --- Ontology (additional reads) ---
  listLineageEdges: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.parentType) params.set("parent_type", filters.parentType);
    if (filters.parentId) params.set("parent_id", String(filters.parentId));
    if (filters.childType) params.set("child_type", filters.childType);
    if (filters.childId) params.set("child_id", String(filters.childId));
    const suffix = params.size ? `?${params.toString()}` : "";
    return request(`/api/ontology/lineage-edges${suffix}`);
  },
  createLineageEdge: (payload) =>
    request("/api/ontology/lineage-edges", { method: "POST", body: JSON.stringify(payload) }),
  deleteLineageEdge: (edgeId) =>
    request(`/api/ontology/lineage-edges/${edgeId}`, { method: "DELETE" }),

  // --- Ontology (create/update/delete) ---
  createOntologyEntity: (endpoint, payload) =>
    request(`/api/ontology/${endpoint}`, { method: "POST", body: JSON.stringify(payload) }),
  updateOntologyEntity: (endpoint, id, payload) =>
    request(`/api/ontology/${endpoint}/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteOntologyEntity: (endpoint, id) =>
    request(`/api/ontology/${endpoint}/${id}`, { method: "DELETE" }),
  listMetricDefinitions: (scope) => {
    const q = scope ? `?scope=${encodeURIComponent(scope)}` : "";
    return request(`/api/metrics/definitions${q}`);
  },

  // --- Experiment Designs ---
  listDesigns: () => request("/api/experiment-designs"),
  createDesign: (payload) =>
    request("/api/experiment-designs", { method: "POST", body: JSON.stringify(payload) }),
  getDesign: (id) => request(`/api/experiment-designs/${id}`),
  updateDesign: (id, payload) =>
    request(`/api/experiment-designs/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteDesign: (id) =>
    request(`/api/experiment-designs/${id}`, { method: "DELETE" }),
  realizeDesign: (id, payload) =>
    request(`/api/experiment-designs/${id}/realize`, { method: "POST", body: JSON.stringify(payload) }),
  duplicateDesign: (id) =>
    request(`/api/experiment-designs/${id}/duplicate`, { method: "POST" }),

  // --- Projects ---
  listProjects: () => request("/api/projects"),
  createProject: (payload) =>
    request("/api/projects", { method: "POST", body: JSON.stringify(payload) }),
  getProject: (projectId) => request(`/api/projects/${projectId}`),
  updateProject: (projectId, payload) =>
    request(`/api/projects/${projectId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteProject: (projectId) =>
    request(`/api/projects/${projectId}`, { method: "DELETE" }),

  // --- Experiments ---
  listExperiments: (projectId) =>
    request(`/api/projects/${projectId}/experiments`),
  createExperiment: (projectId, payload) =>
    request(`/api/projects/${projectId}/experiments`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getExperiment: (experimentId) => request(`/api/experiments/${experimentId}`),
  updateExperiment: (experimentId, payload) =>
    request(`/api/experiments/${experimentId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteExperiment: (experimentId) =>
    request(`/api/experiments/${experimentId}`, { method: "DELETE" }),

  // --- Cells ---
  createCell: (experimentId, payload) =>
    request(`/api/experiments/${experimentId}/cells`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getCell: (cellId) => request(`/api/cells/${cellId}`),
  updateCell: (cellId, payload) =>
    request(`/api/cells/${cellId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCell: (cellId) =>
    request(`/api/cells/${cellId}`, { method: "DELETE" }),
  uploadCyclingData: (cellId, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/api/cells/${cellId}/upload-cycling-data`, {
      method: "POST",
      headers: {},          // let browser set multipart content-type
      body: form,
    });
  },

  // --- Analysis: Workspaces & Cohorts ---
  listStudyWorkspaces: () => request("/api/analysis/study-workspaces"),
  getStudyWorkspace: (workspaceId, refresh = false) =>
    request(`/api/analysis/study-workspaces/${workspaceId}?refresh=${refresh}`),
  createStudyWorkspace: (payload) =>
    request("/api/analysis/study-workspaces", { method: "POST", body: JSON.stringify(payload) }),
  deleteStudyWorkspace: (workspaceId) =>
    request(`/api/analysis/study-workspaces/${workspaceId}`, { method: "DELETE" }),
  listCohortSnapshots: () => request("/api/analysis/cohort-snapshots"),
  getCohortSnapshot: (snapshotId) =>
    request(`/api/analysis/cohort-snapshots/${snapshotId}`),
  createWorkspaceAnnotation: (workspaceId, payload) =>
    request(`/api/analysis/study-workspaces/${workspaceId}/annotations`, { method: "POST", body: JSON.stringify(payload) }),
  deleteWorkspaceAnnotation: (annotationId) =>
    request(`/api/analysis/study-workspaces/annotations/${annotationId}`, { method: "DELETE" }),

  // --- Cohort Builder ---
  getCohortRecords: () => request("/api/analysis/cohort-records"),
  previewCohort: (filters) =>
    request("/api/analysis/cohort-preview", { method: "POST", body: JSON.stringify({ filters }) }),
  createCohortSnapshot: (payload) =>
    request("/api/analysis/cohort-snapshots", { method: "POST", body: JSON.stringify(payload) }),
};
