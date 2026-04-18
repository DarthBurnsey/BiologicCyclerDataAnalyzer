import { api } from "./api.js";

// --- Search & Filter: results column definitions ---
// Declared up-front because state initialization below calls
// loadSfColumnsVisible() which references SF_COLUMN_DEFS.
const SF_COLUMN_DEFS = [
  { key: "experiment_name", label: "Experiment", alwaysVisible: true },
  { key: "project_name", label: "Project" },
  { key: "electrolyte", label: "Electrolyte" },
  { key: "ontology_root_batch_name", label: "Parent batch" },
  { key: "cell_count", label: "Cells" },
  { key: "avg_retention_pct", label: "Retention %", fmt: (v) => v != null ? formatNumber(v, 1) : "—" },
  { key: "avg_fade_rate_pct_per_100_cycles", label: "Fade rate", fmt: (v) => v != null ? formatNumber(v, 2) : "—" },
  { key: "best_cycle_life_80", label: "Cycle life", fmt: (v) => v != null ? Math.round(v) : "—" },
  { key: "tracking_status", label: "Status" },
];

const SF_COLUMNS_STORAGE_KEY = "cs2.sfColumns";

function defaultSfColumnsVisible() {
  const out = {};
  for (const c of SF_COLUMN_DEFS) {
    if (c.alwaysVisible) continue;
    // Default Fade rate OFF to keep table density similar to the legacy layout.
    out[c.key] = c.key !== "avg_fade_rate_pct_per_100_cycles";
  }
  return out;
}

function loadSfColumnsVisible() {
  try {
    const raw = typeof localStorage !== "undefined" ? localStorage.getItem(SF_COLUMNS_STORAGE_KEY) : null;
    if (!raw) return defaultSfColumnsVisible();
    const parsed = JSON.parse(raw);
    const defaults = defaultSfColumnsVisible();
    return { ...defaults, ...parsed };
  } catch {
    return defaultSfColumnsVisible();
  }
}

const state = {
  currentView: "overview",
  dashboard: null,
  reviewItems: [],
  selectedReviewId: null,
  runs: [],
  selectedRunId: null,
  runDetail: null,
  runProvenance: null,
  runMetrics: null,
  runsTab: "expcompare",
  metricDefinitions: [],
  metricScopeFilter: "all",
  compareRunIds: [],
  compareRunDetails: {},
  compareRunMetrics: {},
  compareLoading: false,
  // Cell comparison
  cellCompareProjects: [],
  cellCompareExperiments: [],
  cellCompareCells: [],
  cellCompareSelectedIds: [],
  cellCompareData: {},
  ontologyTab: "materials",
  ontologyEntities: [],
  ontologySelectedId: null,
  ontologyDetail: null,
  // Projects
  projects: [],
  selectedProjectId: null,
  experiments: [],
  selectedExperimentId: null,
  experimentDetail: null,
  currentCells: [],
  // Cohort builder / Search & Filter
  cohortRecords: [],
  cohortFilterOptions: {},
  cohortPreviewResult: null,
  sfActiveTab: "my",
  sfSelectedIds: new Set(),
  sfFilters: {
    projectIds: new Set(),
    rootBatches: new Set(),
    electrolytes: new Set(),
    statuses: new Set(),
    search: "",
    minRetention: null,
    minCE: null,
    maxFade: null,
    minCycleLife: null,
    dateFrom: "",
    dateTo: "",
  },
  sfFilterSearch: {
    projectIds: "",
    rootBatches: "",
    electrolytes: "",
    statuses: "",
  },
  sfColumnsVisible: loadSfColumnsVisible(),
  sfFilteredRecords: [],
  sfLoaded: false,
  // Analytics
  analyticsRecords: [],
  analyticsFilterOptions: {},
  analyticsFiltered: [],
  analyticsSortCol: "avg_retention_pct",
  analyticsSortAsc: false,
  analyticsTableSearch: "",
  analyticsStudioTab: "distribution",
  analyticsScatterX: "avg_retention_pct",
  analyticsScatterY: "avg_fade_rate_pct_per_100_cycles",
  analyticsScatterTrendline: true,
  analyticsHistogramMetric: "avg_retention_pct",
  analyticsHistogramBins: "auto",
  analyticsGroupBy: "",
  analyticsExcludeOutliers: true,
  analyticsExcludedIds: [],
  // Experiment Comparison (cross-project)
  expCompareProjects: [],
  expCompareExperiments: [],
  expCompareSelectedIds: [],
  expCompareLoadedData: {},
  // Master Table
  masterTableRecords: [],
  masterTableFiltered: [],
  masterTableSortCol: "experiment_name",
  masterTableSortAsc: true,
  masterTableColumnFilters: {},
  masterTableColumns: { performance: true, processing: true, materials: true },
  masterTableLoaded: false,
  // Workspaces
  studyWorkspaces: [],
  cohortSnapshots: [],
  selectedWorkspaceId: null,
  selectedCohortSnapshotId: null,
  workspaceDetail: null,
  cohortSnapshotDetail: null,
  // Workspace widget system
  workspaceWidgets: {},
  workspaceActiveWidgetId: null,
  // Experiment Designer
  designs: [],
  selectedDesignId: null,
  designerDirty: false,
  ontologyMaterials: [],
};

const elements = {};

document.addEventListener("DOMContentLoaded", async () => {
  cacheElements();
  ensureDynamicPanels();
  ensureReviewResolutionChoices();
  bindEvents();
  switchView("overview");
  await refreshConnectivity();
  await refreshAll();
});

function cacheElements() {
  const ids = [
    "apiStatusBadge",
    "apiStatusText",
    "refreshAllButton",
    "viewNav",
    "view-overview",
    "view-review",
    "view-runs",
    "view-ontology",
    "view-projects",
    "view-analytics",
    "view-workspaces",
    "overviewCards",
    "overviewActiveRuns",
    "overviewRecentAnomalies",
    "overviewRecentReports",
    "runCollectorButton",
    "reviewQueueList",
    "reviewQueueEmpty",
    "reviewDetailPanel",
    "reviewItemTitle",
    "reviewArtifactMeta",
    "reviewPayloadJson",
    "reviewResolveForm",
    "reviewResolution",
    "reviewedBy",
    "reviewChannelId",
    "reviewCellId",
    "reviewCellBuildId",
    "reviewFilePattern",
    "reviewReason",
    "reviewReprocessNow",
    "reviewRejectButton",
    "runsList",
    "runDetailPanel",
    "runSummaryMeta",
    "runMetricsList",
    "runProvenanceList",
    "runChartsContainer",
    "runsSubNav",
    "runsInspectorPane",
    "runsRegistryPane",
    "metricRegistryList",
    "runsComparePane",
    "compareRunPickerList",
    "compareRunsButton",
    "compareClearButton",
    "compareDetailPanel",
    "compareSummaryMeta",
    "compareChartsContainer",
    "compareMetricsTable",
    "cellComparePane",
    "cellCompareProject",
    "cellCompareExperiment",
    "cellComparePickerList",
    "cellCompareButton",
    "cellCompareClearButton",
    "cellCompareDetailPanel",
    "cellCompareSummaryMeta",
    "cellCompareChartsContainer",
    "cellCompareMetricsTable",
    "expComparePane",
    "expCompareProjectFilter",
    "expComparePickerList",
    "expCompareButton",
    "expCompareClearButton",
    "expCompareSummaryMeta",
    "expCompareChartsContainer",
    "expCompareMetricsTable",
    "ontologySubNav",
    "ontologyFilterInput",
    "ontologyListTitle",
    "ontologyListSubtitle",
    "ontologyEntityList",
    "ontologyDetailPanel",
    "ontologyDetailTitle",
    "ontologyDetailSubtitle",
    "ontologyDetailBody",
    "ontologyLineageContainer",
    "exportRunCycleData",
    "exportOntologyList",
    "exportCellsData",
    "ontologyCreateDetails",
    "ontologyCreateForm",
    "ontologyCreateFields",
    "ontologyDetailActions",
    "ontologyEditButton",
    "ontologyDeleteButton",
    "ontologyEditFormContainer",
    "ontologySummaryBar",
    "ontologyGlobalSearch",
    // Projects / Finder
    "finderBreadcrumb",
    "finderColProjects",
    "finderColExperiments",
    "finderColDetail",
    "projectsList",
    "createProjectForm",
    "createProjectDetails",
    "newProjectName",
    "newProjectType",
    "newProjectDescription",
    "projectDetailPanel",
    "projectDetailTitle",
    "projectDetailMeta",
    "projectDetailBody",
    "experimentsList",
    "createExperimentDetails",
    "createExperimentForm",
    "newExperimentName",
    "newExperimentDate",
    "newExperimentDisc",
    "newExperimentNotes",
    "cellsSection",
    "cellsSectionTitle",
    "cellsSectionMeta",
    "cellsTableContainer",
    "experimentChartsContainer",
    "experimentStatsPanel",
    "experimentStatsMeta",
    "experimentStatsSummary",
    "experimentStatsCharts",
    "experimentFadeRateTable",
    "cellDetailPanel",
    "cellDetailTitle",
    "cellDetailClose",
    "cellDetailMeta",
    "cellDetailChartsContainer",
    "cellDetailDataTable",
    "projectSearchInput",
    "experimentSearchInput",
    "createCellDetails",
    "createCellForm",
    "newCellName",
    "newCellLoading",
    "newCellAM",
    "newCellElectrolyte",
    "newCellSeparator",
    "newCellFormation",
    // Workspaces
    "workspacesList",
    "cohortSnapshotsList",
    "workspaceDetailPanel",
    "workspaceDetailTitle",
    "workspaceDetailMeta",
    "workspaceDetailBody",
    "workspaceMembersContainer",
    "workspaceAnnotationsContainer",
    // Widget canvas
    "widgetCanvas",
    "widgetGrid",
    "addWidgetButton",
    "manageWidgetsSidebar",
    "manageWidgetsClose",
    "wWidgetType",
    "wDataType",
    "wGroupCount",
    "wGroupBy",
    "wGroupingsList",
    "wClearGroupings",
    "wXAxis",
    "wXAxisWrap",
    "wYAxis",
    "wClearMetrics",
    "wFiltersList",
    "wAddFilter",
    "wClearFilters",
    "wCycleSelectorList",
    "wAddCycleSelector",
    "wClearCycleSelector",
    "wGenerateButton",
    // Workspaces sub-nav & Search & Filter pane
    "workspacesSubNav",
    "wsPaneMy",
    "wsPaneSearch",
    "sfResetAll",
    "sfSearchInput",
    "sfAccordion",
    "sfProjectFilter",
    "sfProjectCount",
    "sfBatchFilter",
    "sfBatchCount",
    "sfElectrolyteFilter",
    "sfElectrolyteCount",
    "sfStatusFilter",
    "sfStatusCount",
    "sfMinRetention",
    "sfMinCE",
    "sfMaxFade",
    "sfMinCycleLife",
    "sfDateFrom",
    "sfDateTo",
    "sfDateCount",
    "sfColumnsBtn",
    "sfColumnsMenu",
    "sfSelectionCount",
    "sfResultsCount",
    "sfClearSelectionBtn",
    "sfCreateWorkspaceBtn",
    "sfCreateForm",
    "sfWorkspaceName",
    "sfWorkspaceDesc",
    "sfConfirmCreateBtn",
    "sfCancelCreateBtn",
    "sfResultsTableContainer",
    "workspaceActions",
    "openAsWorkspaceButton",
    "deleteWorkspaceButton",
    // Master Table
    "masterTableToggle",
    "masterTableView",
    "projectsBrowseView",
    "masterTableContainer",
    "masterTableCount",
    "masterTableExport",
    "masterTableFilters",
    // Report
    "reportOverlay",
    "reportContent",
    "reportPrintButton",
    "reportCloseButton",
    "generateReportButton",
    // Analytics
    "analyticsRefreshButton",
    "analyticsExportButton",
    "analyticsKpiBar",
    "analyticsFilterBar",
    "analyticsFilterProject",
    "analyticsFilterElectrolyte",
    "analyticsFilterBatch",
    "analyticsFilterStatus",
    "analyticsFilterApply",
    "analyticsFilterClear",
    "analyticsOutlierToggle",
    "analyticsActiveFilters",
    "analyticsStudio",
    "analyticsStudioCharts",
    "studioScatterConfig",
    "studioScatterX",
    "studioScatterY",
    "studioScatterTrendline",
    "studioHistogramConfig",
    "studioHistogramMetric",
    "studioHistogramBins",
    "studioGroupBy",
    "analyticsStatsPanel",
    "analyticsStatsMeta",
    "analyticsStatsBody",
    "analyticsTableMeta",
    "analyticsTableContainer",
    "analyticsTableSearch",
    "workspaceAnnotationFormContainer",
    "workspaceAnnotationForm",
    "annotationTitle",
    "annotationBody",
    "annotationType",
    "toastRegion",
    // Experiment Designer
    "ontologyCatalogView",
    "experimentDesignerView",
    "designerFilterInput",
    "designerList",
    "designerListCount",
    "designerNewButton",
    "designerFormPanel",
    "designerEmptyState",
    "designerFormContent",
    "designerName",
    "designerStatusBadge",
    "designerTimestamp",
    "designerSaveButton",
    "designerDuplicateButton",
    "designerDeleteButton",
    "designerElectrodeRole",
    "designerTargetProject",
    "designerFormulationRows",
    "designerAddComponent",
    "designerFormulationTotal",
    "designerDiscDiameter",
    "designerLoading",
    "designerThickness",
    "designerPressedThickness",
    "designerPorosity",
    "designerSolidsContent",
    "designerActiveMassDensity",
    "designerSlurryDensity",
    "designerFormFactor",
    "designerCurrentCollector",
    "designerElectrolyte",
    "designerSeparator",
    "designerFormationProtocol",
    "designerCyclingProtocol",
    "designerFormationCycles",
    "designerTemperature",
    "designerCutoffLower",
    "designerCutoffUpper",
    "designerCRateCharge",
    "designerCRateDischarge",
    "designerNumCells",
    "designerNamingPattern",
    "designerTargetEquipment",
    "designerDesignedBy",
    "designerNotes",
    "designerCalcGrid",
    "designerRealizeBar",
    "designerRealizeStatus",
    "designerMarkReady",
    "designerRealizeButton",
  ];

  ids.forEach((id) => {
    elements[id] = document.getElementById(id);
  });
}

function ensureDynamicPanels() {
  if (elements.runDetailPanel && !document.getElementById("runSummaryBody")) {
    const summaryBody = document.createElement("div");
    summaryBody.id = "runSummaryBody";
    summaryBody.className = "summary-body";
    const detailGrid = elements.runDetailPanel.querySelector(".detail-grid");
    if (detailGrid) {
      elements.runDetailPanel.insertBefore(summaryBody, detailGrid);
    } else {
      elements.runDetailPanel.append(summaryBody);
    }
    elements.runSummaryBody = summaryBody;
  } else {
    elements.runSummaryBody = document.getElementById("runSummaryBody");
  }

  // ontology detail panel is now in the HTML, no dynamic creation needed
}

function ensureReviewResolutionChoices() {
  if (!elements.reviewResolution) {
    return;
  }

  if (!elements.reviewResolution.children.length) {
    const options = [
      ["confirmed", "Confirm mapping"],
      ["rejected", "Reject artifact"],
    ];
    for (const [value, label] of options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      elements.reviewResolution.append(option);
    }
  }

  if (!elements.reviewedBy.value.trim()) {
    elements.reviewedBy.value = "operator";
  }
}

function bindEvents() {
  elements.viewNav?.addEventListener("click", (event) => {
    const button = event.target.closest(".view-tab");
    if (!button) {
      return;
    }
    switchView(button.dataset.view || "overview");
  });

  elements.refreshAllButton?.addEventListener("click", async () => {
    await refreshAll();
  });

  elements.runCollectorButton?.addEventListener("click", async () => {
    await withButtonBusy(elements.runCollectorButton, async () => {
      const result = await api.runCollectorOnce();
      showToast(
        `Collector ran: ${result.files_ingested} ingested, ${result.files_failed} failed.`,
        "success",
      );
      await refreshAll();
    });
  });

  elements.overviewActiveRuns?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-run-id]");
    if (!button) {
      return;
    }
    switchView("runs");
    await selectRun(Number(button.dataset.runId));
  });

  elements.reviewQueueList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-review-id]");
    if (!button) {
      return;
    }
    selectReview(Number(button.dataset.reviewId));
  });

  elements.reviewResolveForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitReview(elements.reviewResolution?.value || "confirmed");
  });

  elements.reviewRejectButton?.addEventListener("click", async (event) => {
    event.preventDefault();
    await submitReview("rejected");
  });

  elements.runsList?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-run-id]");
    if (!button) {
      return;
    }
    const runId = Number(button.dataset.runId);
    await selectRun(runId);
  });

  elements.runsSubNav?.addEventListener("click", async (event) => {
    const tab = event.target.closest(".sub-nav-tab");
    if (!tab) return;
    const tabName = tab.dataset.runsTab;
    if (tabName === state.runsTab) return;
    state.runsTab = tabName;
    elements.runsSubNav.querySelectorAll(".sub-nav-tab").forEach((b) =>
      b.classList.toggle("is-active", b.dataset.runsTab === tabName));
    elements.runsInspectorPane.hidden = tabName !== "inspector";
    elements.runsRegistryPane.hidden = tabName !== "registry";
    if (elements.runsComparePane) {
      elements.runsComparePane.hidden = tabName !== "compare";
    }
    if (elements.cellComparePane) {
      elements.cellComparePane.hidden = tabName !== "cellcompare";
    }
    if (elements.expComparePane) {
      elements.expComparePane.hidden = tabName !== "expcompare";
    }
    if (tabName === "registry" && !state.metricDefinitions.length) {
      await loadMetricDefinitions();
    }
    if (tabName === "compare") {
      renderCompareRunPicker();
    }
    if (tabName === "cellcompare" && !state.cellCompareProjects.length) {
      await loadCellCompareProjects();
    }
    if (tabName === "expcompare" && !state.expCompareProjects.length) {
      await loadExpCompareProjects();
    }
  });

  elements.compareRunPickerList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-compare-run-id]");
    if (!button) return;
    toggleCompareRun(Number(button.dataset.compareRunId));
  });

  elements.compareRunsButton?.addEventListener("click", async () => {
    if (state.compareRunIds.length < 2) return;
    await withButtonBusy(elements.compareRunsButton, loadCompareData);
  });

  elements.compareClearButton?.addEventListener("click", () => {
    clearCompareSelection();
  });

  elements.runsRegistryPane?.addEventListener("click", async (event) => {
    const scopeBtn = event.target.closest(".scope-filter-btn");
    if (!scopeBtn) return;
    state.metricScopeFilter = scopeBtn.dataset.scope;
    elements.runsRegistryPane.querySelectorAll(".scope-filter-btn").forEach((b) =>
      b.classList.toggle("is-active", b.dataset.scope === state.metricScopeFilter));
    renderMetricRegistry();
  });

  elements.ontologySubNav?.addEventListener("click", async (event) => {
    const tab = event.target.closest(".sub-nav-tab");
    if (!tab) return;
    const tabName = tab.dataset.ontoTab;
    if (tabName === state.ontologyTab) return;
    state.ontologyTab = tabName;
    state.ontologySelectedId = null;
    state.ontologyDetail = null;
    elements.ontologySubNav.querySelectorAll(".sub-nav-tab").forEach((b) =>
      b.classList.toggle("is-active", b.dataset.ontoTab === tabName));

    // Toggle between catalog view and designer view
    const isDesigner = tabName === "designer";
    if (elements.ontologyCatalogView) elements.ontologyCatalogView.hidden = isDesigner;
    if (elements.experimentDesignerView) elements.experimentDesignerView.hidden = !isDesigner;

    if (isDesigner) {
      await loadDesignerList();
    } else {
      elements.ontologyFilterInput.value = "";
      if (elements.ontologyGlobalSearch) elements.ontologyGlobalSearch.value = "";
      await loadOntologyTab(tabName);
    }
  });

  elements.ontologyFilterInput?.addEventListener("input", () => {
    renderOntologyEntityList();
  });

  // Global search across all ontology entities
  elements.ontologyGlobalSearch?.addEventListener("input", (event) => {
    clearTimeout(_globalSearchTimeout);
    const query = event.target.value.trim();
    _globalSearchTimeout = setTimeout(() => handleOntologyGlobalSearch(query), 300);
  });

  elements.ontologyEntityList?.addEventListener("click", async (event) => {
    // Handle normal entity click
    const btn = event.target.closest("[data-entity-id]");
    if (btn) {
      await selectOntologyEntity(Number(btn.dataset.entityId));
      return;
    }
    // Handle global search result click — switch to the right tab
    const searchBtn = event.target.closest("[data-search-entity-type]");
    if (searchBtn) {
      const entityType = searchBtn.dataset.searchEntityType;
      const entityId = Number(searchBtn.dataset.searchEntityId);
      const tabMap = {
        material: "materials", cell_build: "cellBuilds", electrode_batch: "batches",
        equipment_asset: "equipment", protocol_version: "protocols", operator: "people",
        process_run: "processRuns", fixture: "equipment", material_lot: "materialLots",
      };
      const targetTab = tabMap[entityType];
      if (targetTab && targetTab !== state.ontologyTab) {
        state.ontologyTab = targetTab;
        elements.ontologySubNav.querySelectorAll(".sub-nav-tab").forEach((b) =>
          b.classList.toggle("is-active", b.dataset.ontoTab === targetTab));
        elements.ontologyGlobalSearch.value = "";
        await loadOntologyTab(targetTab);
      }
      await selectOntologyEntity(entityId);
    }
  });

  elements.ontologyCreateForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const config = ONTOLOGY_TAB_CONFIG[state.ontologyTab];
    if (config?.isLineage) {
      await submitLineageEdgeCreate();
    } else {
      await submitOntologyCreate();
    }
  });

  elements.ontologyEditButton?.addEventListener("click", () => {
    if (ONTOLOGY_TAB_CONFIG[state.ontologyTab]?.isLineage) return; // Lineage edges are immutable
    showOntologyEditForm();
  });

  elements.ontologyDeleteButton?.addEventListener("click", async () => {
    const config = ONTOLOGY_TAB_CONFIG[state.ontologyTab];
    if (config?.isLineage) {
      await deleteLineageEdge();
    } else {
      await deleteOntologyEntity();
    }
  });

  // --- Experiment Designer ---
  elements.designerNewButton?.addEventListener("click", () => createNewDesign());
  elements.designerSaveButton?.addEventListener("click", () => saveCurrentDesign());
  elements.designerDuplicateButton?.addEventListener("click", () => duplicateCurrentDesign());
  elements.designerDeleteButton?.addEventListener("click", () => deleteCurrentDesign());
  elements.designerAddComponent?.addEventListener("click", () => addFormulationRow());
  elements.designerMarkReady?.addEventListener("click", () => markDesignReady());
  elements.designerRealizeButton?.addEventListener("click", () => realizeCurrentDesign());

  elements.designerFilterInput?.addEventListener("input", () => renderDesignerList());

  elements.designerList?.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-design-id]");
    if (btn) await selectDesign(Number(btn.dataset.designId));
  });

  // Live calculation triggers — debounced
  const calcInputIds = [
    "designerDiscDiameter", "designerLoading", "designerThickness",
    "designerPressedThickness", "designerPorosity", "designerActiveMassDensity",
    "designerSlurryDensity",
  ];
  calcInputIds.forEach((id) => {
    elements[id]?.addEventListener("input", () => updateDesignerCalculations());
  });

  // --- Projects ---
  elements.projectsList?.addEventListener("click", async (event) => {
    // Rename project
    const renameBtn = event.target.closest("[data-rename-project]");
    if (renameBtn) {
      event.stopPropagation();
      const projId = Number(renameBtn.dataset.renameProject);
      const proj = state.projects.find((p) => p.id === projId);
      const newName = window.prompt("Rename project:", proj?.name || "");
      if (newName != null && newName.trim()) {
        try {
          await api.updateProject(projId, { name: newName.trim() });
          showToast("Project renamed.", "success");
          await loadProjects();
        } catch (err) { showToast(`Rename failed: ${err.message}`, "error"); }
      }
      return;
    }
    // Delete project
    const deleteBtn = event.target.closest("[data-delete-project]");
    if (deleteBtn) {
      event.stopPropagation();
      const projId = Number(deleteBtn.dataset.deleteProject);
      const proj = state.projects.find((p) => p.id === projId);
      if (!window.confirm(`Delete project "${proj?.name || ""}"? All experiments and cells will be deleted.`)) return;
      try {
        await api.deleteProject(projId);
        showToast("Project deleted.", "success");
        if (state.selectedProjectId === projId) {
          state.selectedProjectId = null;
          state.selectedExperimentId = null;
          elements.finderColExperiments?.classList.add("finder-col--hidden");
          elements.finderColDetail?.classList.add("finder-col--hidden");
          updateFinderBreadcrumb(null, null);
        }
        await loadProjects();
      } catch (err) { showToast(`Delete failed: ${err.message}`, "error"); }
      return;
    }
    // Normal select
    const button = event.target.closest("[data-project-id]");
    if (!button) return;
    await selectProject(Number(button.dataset.projectId));
  });

  elements.createProjectForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await withFormBusy(elements.createProjectForm, async () => {
      const payload = {
        name: elements.newProjectName.value.trim(),
        project_type: elements.newProjectType.value,
        description: emptyToNull(elements.newProjectDescription.value),
      };
      await api.createProject(payload);
      showToast(`Project "${payload.name}" created.`, "success");
      elements.createProjectForm.reset();
      elements.createProjectDetails.open = false;
      await loadProjects();
    });
  });

  elements.experimentsList?.addEventListener("click", async (event) => {
    // Rename experiment
    const renameBtn = event.target.closest("[data-rename-experiment]");
    if (renameBtn) {
      event.stopPropagation();
      const expId = Number(renameBtn.dataset.renameExperiment);
      const exp = state.experiments.find((e) => e.id === expId);
      const newName = window.prompt("Rename experiment:", exp?.name || "");
      if (newName != null && newName.trim()) {
        try {
          await api.updateExperiment(expId, { name: newName.trim() });
          showToast("Experiment renamed.", "success");
          await loadExperiments(state.selectedProjectId);
          if (state.selectedExperimentId === expId) await selectExperiment(expId);
        } catch (err) { showToast(`Rename failed: ${err.message}`, "error"); }
      }
      return;
    }
    // Delete experiment
    const deleteBtn = event.target.closest("[data-delete-experiment]");
    if (deleteBtn) {
      event.stopPropagation();
      const expId = Number(deleteBtn.dataset.deleteExperiment);
      const exp = state.experiments.find((e) => e.id === expId);
      if (!window.confirm(`Delete experiment "${exp?.name || ""}"? All cells will be deleted too.`)) return;
      try {
        await api.deleteExperiment(expId);
        showToast("Experiment deleted.", "success");
        if (state.selectedExperimentId === expId) {
          state.selectedExperimentId = null;
          state.experimentDetail = null;
          elements.finderColDetail?.classList.add("finder-col--hidden");
        }
        await loadExperiments(state.selectedProjectId);
      } catch (err) { showToast(`Delete failed: ${err.message}`, "error"); }
      return;
    }
    // Normal select
    const button = event.target.closest("[data-experiment-id]");
    if (!button) return;
    await selectExperiment(Number(button.dataset.experimentId));
  });

  elements.createExperimentForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.selectedProjectId) return;
    await withFormBusy(elements.createExperimentForm, async () => {
      const payload = {
        name: elements.newExperimentName.value.trim(),
        experiment_date: emptyToNull(elements.newExperimentDate.value),
        disc_diameter_mm: elements.newExperimentDisc.value ? Number(elements.newExperimentDisc.value) : 15.0,
        notes: emptyToNull(elements.newExperimentNotes.value),
      };
      await api.createExperiment(state.selectedProjectId, payload);
      showToast(`Experiment "${payload.name}" created.`, "success");
      elements.createExperimentForm.reset();
      elements.createExperimentDetails.open = false;
      await loadExperiments(state.selectedProjectId);
    });
  });

  elements.createCellForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.selectedExperimentId) return;
    await withFormBusy(elements.createCellForm, async () => {
      const payload = {
        cell_name: elements.newCellName.value.trim(),
        loading: elements.newCellLoading.value ? Number(elements.newCellLoading.value) : null,
        active_material_pct: elements.newCellAM.value ? Number(elements.newCellAM.value) : null,
        electrolyte: emptyToNull(elements.newCellElectrolyte.value),
        separator: emptyToNull(elements.newCellSeparator.value),
        formation_cycles: elements.newCellFormation.value ? Number(elements.newCellFormation.value) : 4,
      };
      await api.createCell(state.selectedExperimentId, payload);
      showToast(`Cell "${payload.cell_name}" added.`, "success");
      elements.createCellForm.reset();
      elements.createCellDetails.open = false;
      await selectExperiment(state.selectedExperimentId);
    });
  });

  // --- Finder breadcrumb ---
  elements.finderBreadcrumb?.addEventListener("click", (event) => {
    const seg = event.target.closest("[data-breadcrumb]");
    if (!seg || seg.classList.contains("is-active")) return;
    if (seg.dataset.breadcrumb === "root") {
      state.selectedProjectId = null;
      state.selectedExperimentId = null;
      state.experimentDetail = null;
      renderProjectsList();
      elements.finderColExperiments?.classList.add("finder-col--hidden");
      elements.finderColDetail?.classList.add("finder-col--hidden");
      updateFinderBreadcrumb(null, null);
    } else if (seg.dataset.breadcrumb === "project") {
      state.selectedExperimentId = null;
      state.experimentDetail = null;
      renderExperimentsList();
      elements.finderColDetail?.classList.add("finder-col--hidden");
      const projName = elements.projectDetailTitle?.textContent || "Project";
      updateFinderBreadcrumb(projName, null);
    }
  });

  // --- Search filters ---
  elements.projectSearchInput?.addEventListener("input", () => {
    renderProjectsList();
  });

  elements.experimentSearchInput?.addEventListener("input", () => {
    renderExperimentsList();
  });

  // --- Cell detail and cell actions ---
  elements.cellsTableContainer?.addEventListener("click", async (event) => {
    // Upload cycling data
    const uploadBtn = event.target.closest("[data-upload-cell]");
    if (uploadBtn) {
      event.stopPropagation();
      const cellId = Number(uploadBtn.dataset.uploadCell);
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".csv,.xlsx,.xls";
      input.addEventListener("change", async () => {
        const file = input.files[0];
        if (!file) return;
        try {
          await api.uploadCyclingData(cellId, file);
          showToast(`Cycling data uploaded for cell.`, "success");
          await selectExperiment(state.selectedExperimentId);
        } catch (err) { showToast(`Upload failed: ${err.message}`, "error"); }
      });
      input.click();
      return;
    }
    // Edit cell
    const editBtn = event.target.closest("[data-edit-cell]");
    if (editBtn) {
      event.stopPropagation();
      const cellId = Number(editBtn.dataset.editCell);
      const cell = state.currentCells.find((c) => c.id === cellId);
      if (!cell) return;
      showCellEditModal(cell);
      return;
    }
    // Delete cell
    const deleteBtn = event.target.closest("[data-delete-cell]");
    if (deleteBtn) {
      event.stopPropagation();
      const cellId = Number(deleteBtn.dataset.deleteCell);
      const cell = state.currentCells.find((c) => c.id === cellId);
      if (!window.confirm(`Delete cell "${cell?.cell_name || ""}"?`)) return;
      try {
        await api.deleteCell(cellId);
        showToast("Cell deleted.", "success");
        await selectExperiment(state.selectedExperimentId);
      } catch (err) { showToast(`Delete failed: ${err.message}`, "error"); }
      return;
    }
    // Normal row click → cell detail
    const row = event.target.closest("tr[data-cell-index]");
    if (!row) return;
    const cellIndex = Number(row.dataset.cellIndex);
    openCellDetail(cellIndex);
  });

  elements.cellDetailClose?.addEventListener("click", () => {
    if (elements.cellDetailPanel) elements.cellDetailPanel.hidden = true;
  });

  // --- Export CSV ---
  elements.exportRunCycleData?.addEventListener("click", () => exportRunCycleData());
  elements.exportOntologyList?.addEventListener("click", () => exportOntologyEntities());
  elements.exportCellsData?.addEventListener("click", () => exportCellsData());

  // --- Report ---
  elements.generateReportButton?.addEventListener("click", () => generateExperimentReport());
  elements.reportPrintButton?.addEventListener("click", () => {
    window.print();
  });
  elements.reportCloseButton?.addEventListener("click", () => {
    if (elements.reportOverlay) elements.reportOverlay.hidden = true;
    document.body.classList.remove("report-printing");
  });

  // --- Master Table ---
  elements.masterTableToggle?.addEventListener("click", () => {
    const showing = !elements.masterTableView.hidden;
    elements.masterTableView.hidden = showing;
    elements.projectsBrowseView.hidden = !showing;
    if (elements.finderBreadcrumb) elements.finderBreadcrumb.hidden = !showing;
    elements.masterTableToggle.textContent = showing ? "Master Table" : "Browse Projects";
    if (!showing && !state.masterTableLoaded) {
      loadMasterTable();
    }
  });

  elements.masterTableView?.addEventListener("click", (event) => {
    // Column group toggles
    const toggle = event.target.closest("[data-mt-group]");
    if (toggle) {
      const group = toggle.dataset.mtGroup;
      state.masterTableColumns[group] = !state.masterTableColumns[group];
      toggle.classList.toggle("is-active", state.masterTableColumns[group]);
      renderMasterTable();
      return;
    }
    // Sort headers
    const th = event.target.closest("[data-mt-sort]");
    if (th) {
      const col = th.dataset.mtSort;
      if (state.masterTableSortCol === col) {
        state.masterTableSortAsc = !state.masterTableSortAsc;
      } else {
        state.masterTableSortCol = col;
        state.masterTableSortAsc = col === "experiment_name" || col === "project_name";
      }
      renderMasterTable();
      return;
    }
    // Filter pill removal
    const pill = event.target.closest("[data-mt-clear-filter]");
    if (pill) {
      delete state.masterTableColumnFilters[pill.dataset.mtClearFilter];
      applyMasterTableFilters();
      return;
    }
    // Row click-through
    const row = event.target.closest("[data-mt-exp-id]");
    if (row) {
      const projId = Number(row.dataset.mtProjId);
      const expId = Number(row.dataset.mtExpId);
      elements.masterTableView.hidden = true;
      elements.projectsBrowseView.hidden = false;
      if (elements.finderBreadcrumb) elements.finderBreadcrumb.hidden = false;
      elements.masterTableToggle.textContent = "Master Table";
      selectProject(projId).then(() => selectExperiment(expId));
    }
  });

  elements.masterTableView?.addEventListener("input", (event) => {
    const filterInput = event.target.closest("[data-mt-filter]");
    if (!filterInput) return;
    const col = filterInput.dataset.mtFilter;
    const val = filterInput.value.trim().toLowerCase();
    if (val) {
      state.masterTableColumnFilters[col] = val;
    } else {
      delete state.masterTableColumnFilters[col];
    }
    applyMasterTableFilters();
  });

  elements.masterTableExport?.addEventListener("click", () => exportMasterTableCSV());

  elements.compareMetricsTable?.addEventListener("click", (event) => {
    if (event.target.closest("[data-export='compare-metrics']")) {
      exportCompareMetrics();
    }
  });

  // --- Workspaces ---
  elements.workspacesList?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-workspace-id]");
    if (!button) return;
    state.selectedCohortSnapshotId = null;
    await selectWorkspace(Number(button.dataset.workspaceId));
  });

  elements.cohortSnapshotsList?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-snapshot-id]");
    if (!button) return;
    state.selectedWorkspaceId = null;
    await selectCohortSnapshot(Number(button.dataset.snapshotId));
  });

  elements.openAsWorkspaceButton?.addEventListener("click", async () => {
    await openSnapshotAsWorkspace();
  });

  elements.deleteWorkspaceButton?.addEventListener("click", async () => {
    await deleteCurrentWorkspace();
  });

  elements.workspaceAnnotationForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitWorkspaceAnnotation();
  });

  elements.workspaceAnnotationsContainer?.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-delete-annotation-id]");
    if (!btn) return;
    await deleteAnnotation(Number(btn.dataset.deleteAnnotationId));
  });

  // --- Widget Canvas ---
  elements.addWidgetButton?.addEventListener("click", () => {
    openNewWidgetSidebar();
  });

  elements.manageWidgetsClose?.addEventListener("click", () => {
    closeManageWidgetsSidebar();
  });

  elements.wGenerateButton?.addEventListener("click", () => {
    generateActiveWidget();
  });

  elements.wDataType?.addEventListener("change", () => {
    syncWidgetSidebarToDataType();
  });

  elements.wClearGroupings?.addEventListener("click", () => {
    if (elements.wGroupBy) elements.wGroupBy.value = "";
  });

  elements.wClearMetrics?.addEventListener("click", () => {
    if (elements.wXAxis) elements.wXAxis.value = "cycle_number";
    if (elements.wYAxis) elements.wYAxis.value = "capacity_retention";
  });

  elements.wAddFilter?.addEventListener("click", () => {
    addWidgetFilterRow();
  });

  elements.wClearFilters?.addEventListener("click", () => {
    if (elements.wFiltersList) elements.wFiltersList.innerHTML = "";
  });

  elements.wAddCycleSelector?.addEventListener("click", () => {
    addWidgetCycleSelectorRow();
  });

  elements.wClearCycleSelector?.addEventListener("click", () => {
    if (elements.wCycleSelectorList) elements.wCycleSelectorList.innerHTML = "";
  });

  elements.widgetGrid?.addEventListener("click", (event) => {
    const editBtn = event.target.closest("[data-edit-widget]");
    if (editBtn) {
      openEditWidgetSidebar(editBtn.dataset.editWidget);
      return;
    }
    const deleteBtn = event.target.closest("[data-delete-widget]");
    if (deleteBtn) {
      deleteWidget(deleteBtn.dataset.deleteWidget);
    }
  });

  // --- Workspaces sub-tabs ---
  elements.workspacesSubNav?.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-ws-tab]");
    if (!tab) return;
    switchWorkspacesTab(tab.dataset.wsTab);
  });

  // --- Search & Filter ---
  elements.sfSearchInput?.addEventListener("input", debounce(() => {
    state.sfFilters.search = elements.sfSearchInput.value.trim();
    applySfFilters();
  }, 200));

  const numericInputs = [
    [elements.sfMinRetention, "minRetention"],
    [elements.sfMinCE, "minCE"],
    [elements.sfMaxFade, "maxFade"],
    [elements.sfMinCycleLife, "minCycleLife"],
  ];
  numericInputs.forEach(([el, key]) => {
    el?.addEventListener("input", debounce(() => {
      const val = el.value.trim();
      state.sfFilters[key] = val === "" ? null : Number(val);
      applySfFilters();
    }, 200));
  });

  const dateInputs = [
    [elements.sfDateFrom, "dateFrom"],
    [elements.sfDateTo, "dateTo"],
  ];
  dateInputs.forEach(([el, key]) => {
    el?.addEventListener("change", () => {
      state.sfFilters[key] = el.value || "";
      applySfFilters();
    });
  });

  elements.sfResetAll?.addEventListener("click", () => {
    resetSfFilters();
  });

  // --- Search & Filter: within-section search inputs (event delegation) ---
  elements.sfAccordion?.addEventListener("input", (event) => {
    const searchEl = event.target.closest('input[data-sf-filter-search]');
    if (!searchEl) return;
    const key = searchEl.dataset.sfFilterSearch;
    state.sfFilterSearch[key] = searchEl.value.toLowerCase().trim();
    applySfFilterSectionSearch(key);
  });

  // --- Search & Filter: Column picker ---
  elements.sfColumnsBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleSfColumnsMenu();
  });

  elements.sfColumnsMenu?.addEventListener("change", (event) => {
    const cb = event.target.closest('input[type="checkbox"][data-sf-col]');
    if (!cb) return;
    state.sfColumnsVisible[cb.dataset.sfCol] = cb.checked;
    persistSfColumnsVisible();
    renderSfResults();
  });

  document.addEventListener("click", (event) => {
    if (!elements.sfColumnsMenu || elements.sfColumnsMenu.hidden) return;
    if (
      event.target === elements.sfColumnsBtn ||
      elements.sfColumnsBtn?.contains(event.target) ||
      elements.sfColumnsMenu.contains(event.target)
    ) {
      return;
    }
    closeSfColumnsMenu();
  });

  elements.sfResultsTableContainer?.addEventListener("change", (event) => {
    const cb = event.target.closest('input[type="checkbox"][data-sf-row]');
    if (cb) {
      const id = Number(cb.dataset.sfRow);
      if (cb.checked) state.sfSelectedIds.add(id);
      else state.sfSelectedIds.delete(id);
      updateSfSelectionUi();
      return;
    }
    const selectAll = event.target.closest('input[type="checkbox"][data-sf-select-all]');
    if (selectAll) {
      const checked = selectAll.checked;
      state.sfFilteredRecords.forEach((r) => {
        if (checked) state.sfSelectedIds.add(r.experiment_id);
        else state.sfSelectedIds.delete(r.experiment_id);
      });
      renderSfResults();
      updateSfSelectionUi();
    }
  });

  elements.sfClearSelectionBtn?.addEventListener("click", () => {
    state.sfSelectedIds.clear();
    renderSfResults();
    updateSfSelectionUi();
  });

  elements.sfCreateWorkspaceBtn?.addEventListener("click", () => {
    if (!state.sfSelectedIds.size) return;
    if (elements.sfCreateForm) elements.sfCreateForm.hidden = false;
    elements.sfWorkspaceName?.focus();
  });

  elements.sfCancelCreateBtn?.addEventListener("click", () => {
    if (elements.sfCreateForm) elements.sfCreateForm.hidden = true;
    if (elements.sfWorkspaceName) elements.sfWorkspaceName.value = "";
    if (elements.sfWorkspaceDesc) elements.sfWorkspaceDesc.value = "";
  });

  elements.sfConfirmCreateBtn?.addEventListener("click", async () => {
    await createWorkspaceFromSelection();
  });

  // Analytics
  elements.analyticsRefreshButton?.addEventListener("click", async () => {
    await withButtonBusy(elements.analyticsRefreshButton, loadAnalytics);
  });
  elements.analyticsFilterApply?.addEventListener("click", () => {
    applyAnalyticsFilters();
  });
  elements.analyticsFilterClear?.addEventListener("click", () => {
    clearAnalyticsFilters();
  });
  elements.analyticsOutlierToggle?.addEventListener("change", () => {
    state.analyticsExcludeOutliers = elements.analyticsOutlierToggle.checked;
    applyAnalyticsFilters();
  });
  elements.analyticsExportButton?.addEventListener("click", () => {
    exportAnalyticsCSV();
  });

  // Studio tab switching
  elements.analyticsStudio?.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-studio-tab]");
    if (tab) {
      const tabName = tab.dataset.studioTab;
      state.analyticsStudioTab = tabName;
      elements.analyticsStudio.querySelectorAll(".studio-tab").forEach((t) =>
        t.classList.toggle("is-active", t.dataset.studioTab === tabName)
      );
      // Show/hide config panels
      if (elements.studioScatterConfig) elements.studioScatterConfig.hidden = tabName !== "scatter";
      if (elements.studioHistogramConfig) elements.studioHistogramConfig.hidden = tabName !== "histogram";
      renderAnalyticsStudio();
    }
  });

  // Studio scatter config
  elements.studioScatterX?.addEventListener("change", () => {
    state.analyticsScatterX = elements.studioScatterX.value;
    if (state.analyticsStudioTab === "scatter") renderAnalyticsStudio();
  });
  elements.studioScatterY?.addEventListener("change", () => {
    state.analyticsScatterY = elements.studioScatterY.value;
    if (state.analyticsStudioTab === "scatter") renderAnalyticsStudio();
  });
  elements.studioScatterTrendline?.addEventListener("change", () => {
    state.analyticsScatterTrendline = elements.studioScatterTrendline.checked;
    if (state.analyticsStudioTab === "scatter") renderAnalyticsStudio();
  });

  // Studio histogram config
  elements.studioHistogramMetric?.addEventListener("change", () => {
    state.analyticsHistogramMetric = elements.studioHistogramMetric.value;
    if (state.analyticsStudioTab === "histogram") renderAnalyticsStudio();
  });
  elements.studioHistogramBins?.addEventListener("change", () => {
    state.analyticsHistogramBins = elements.studioHistogramBins.value;
    if (state.analyticsStudioTab === "histogram") renderAnalyticsStudio();
  });

  // Studio group-by
  elements.studioGroupBy?.addEventListener("change", () => {
    state.analyticsGroupBy = elements.studioGroupBy.value;
    renderAnalyticsStudio();
  });

  // Table search
  elements.analyticsTableSearch?.addEventListener("input", () => {
    state.analyticsTableSearch = elements.analyticsTableSearch.value;
    renderAnalyticsTable();
  });

  // Table sort + row click + exclude
  elements.analyticsTableContainer?.addEventListener("click", (event) => {
    // Exclude button
    const excludeBtn = event.target.closest("[data-exclude-exp-id]");
    if (excludeBtn) {
      const expId = Number(excludeBtn.dataset.excludeExpId);
      if (!state.analyticsExcludedIds.includes(expId)) {
        state.analyticsExcludedIds.push(expId);
        applyAnalyticsFilters();
        showToast("Experiment excluded from analytics.", "info");
      }
      return;
    }
    const th = event.target.closest("[data-sort-col]");
    if (th) {
      const col = th.dataset.sortCol;
      if (state.analyticsSortCol === col) {
        state.analyticsSortAsc = !state.analyticsSortAsc;
      } else {
        state.analyticsSortCol = col;
        state.analyticsSortAsc = col === "experiment_name" || col === "project_name";
      }
      renderAnalyticsTable();
      return;
    }
    const row = event.target.closest("[data-analytics-exp-id]");
    if (row) {
      const expId = Number(row.dataset.analyticsExpId);
      const projId = Number(row.dataset.analyticsProjectId);
      if (projId) {
        switchView("projects");
        selectProject(projId).then(() => selectExperiment(expId));
      }
    }
  });

  // Cell comparison
  elements.cellCompareProject?.addEventListener("change", async () => {
    const projId = elements.cellCompareProject.value;
    elements.cellCompareExperiment.innerHTML = '<option value="">Choose experiment…</option>';
    elements.cellCompareExperiment.disabled = !projId;
    elements.cellComparePickerList.innerHTML = "";
    state.cellCompareSelectedIds = [];
    updateCellCompareButton();
    if (projId) {
      const exps = await api.listExperiments(Number(projId));
      state.cellCompareExperiments = exps;
      exps.forEach((e) => {
        const opt = document.createElement("option");
        opt.value = e.id;
        opt.textContent = e.name || e.cell_name || `Experiment #${e.id}`;
        elements.cellCompareExperiment.append(opt);
      });
    }
  });

  elements.cellCompareExperiment?.addEventListener("change", async () => {
    const expId = elements.cellCompareExperiment.value;
    state.cellCompareSelectedIds = [];
    state.cellCompareCells = [];
    elements.cellComparePickerList.innerHTML = "";
    updateCellCompareButton();
    if (expId) {
      const exp = await api.getExperiment(Number(expId));
      let cells = exp.cells || [];
      if (!cells.length && exp.data_json) {
        try {
          const parsed = typeof exp.data_json === "string" ? JSON.parse(exp.data_json) : exp.data_json;
          cells = parsed.cells || [];
        } catch (_) {}
      }
      state.cellCompareCells = cells;
      renderCellComparePicker();
    }
  });

  elements.cellComparePickerList?.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-cc-cell-idx]");
    if (!btn) return;
    const idx = Number(btn.dataset.ccCellIdx);
    const pos = state.cellCompareSelectedIds.indexOf(idx);
    if (pos >= 0) {
      state.cellCompareSelectedIds.splice(pos, 1);
    } else if (state.cellCompareSelectedIds.length < 8) {
      state.cellCompareSelectedIds.push(idx);
    }
    renderCellComparePicker();
    updateCellCompareButton();
  });

  elements.cellCompareButton?.addEventListener("click", () => {
    if (state.cellCompareSelectedIds.length >= 2) renderCellCompareCharts();
  });

  elements.cellCompareClearButton?.addEventListener("click", () => {
    state.cellCompareSelectedIds = [];
    renderCellComparePicker();
    updateCellCompareButton();
    if (elements.cellCompareChartsContainer) elements.cellCompareChartsContainer.innerHTML = "";
    if (elements.cellCompareMetricsTable) elements.cellCompareMetricsTable.innerHTML = "";
    if (elements.cellCompareSummaryMeta) elements.cellCompareSummaryMeta.textContent = "Select cells and click Compare";
  });

  // Experiment comparison (cross-project)
  elements.expCompareProjectFilter?.addEventListener("change", () => {
    renderExpComparePickerList();
  });

  elements.expComparePickerList?.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-exp-compare-id]");
    if (!btn) return;
    const expId = Number(btn.dataset.expCompareId);
    const pos = state.expCompareSelectedIds.indexOf(expId);
    if (pos >= 0) {
      state.expCompareSelectedIds.splice(pos, 1);
    } else if (state.expCompareSelectedIds.length < 8) {
      state.expCompareSelectedIds.push(expId);
    } else {
      showToast("Maximum 8 experiments for comparison.", "warn");
      return;
    }
    renderExpComparePickerList();
    updateExpCompareButton();
  });

  elements.expCompareButton?.addEventListener("click", async () => {
    if (state.expCompareSelectedIds.length < 2) return;
    await withButtonBusy(elements.expCompareButton, loadExpCompareData);
  });

  elements.expCompareClearButton?.addEventListener("click", () => {
    state.expCompareSelectedIds = [];
    state.expCompareLoadedData = {};
    renderExpComparePickerList();
    updateExpCompareButton();
    if (elements.expCompareChartsContainer) elements.expCompareChartsContainer.innerHTML = "";
    if (elements.expCompareMetricsTable) elements.expCompareMetricsTable.innerHTML = "";
    if (elements.expCompareSummaryMeta) elements.expCompareSummaryMeta.textContent = "Select experiments and click Compare";
  });
}

async function refreshAll() {
  await Promise.allSettled([
    refreshConnectivity(),
    loadOverview(),
    loadReviewQueue(),
    loadRuns(),
    loadOntologyTab(state.ontologyTab),
    loadOntologySummary(),
    loadProjects(),
    loadWorkspacesAndCohorts(),
  ]);
}

async function refreshConnectivity() {
  setApiStatus("checking", "Checking backend");
  try {
    const health = await api.health();
    setApiStatus("connected", `v${health.version}`);
  } catch (error) {
    setApiStatus("disconnected", "FastAPI backend unavailable");
    showToast(`Backend check failed: ${error.message}`, "warning");
  }
}

function setApiStatus(kind, message) {
  if (elements.apiStatusBadge) {
    elements.apiStatusBadge.className = `status-badge status-badge--${kind}`;
  }
  if (elements.apiStatusText) {
    elements.apiStatusText.textContent = message;
  }
}

function switchView(viewName) {
  state.currentView = viewName;
  document.querySelectorAll(".view-tab").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === viewName);
  });
  ["projects", "workspaces", "overview", "review", "runs", "analytics", "ontology"].forEach((viewId) => {
    const section = elements[`view-${viewId}`];
    if (section) {
      section.hidden = viewId !== viewName;
      section.classList.toggle("is-active", viewId === viewName);
    }
  });
  // Lazy-load analytics on first visit
  if (viewName === "analytics" && !state.analyticsRecords.length) {
    loadAnalytics();
  }
  // Lazy-load comparison data for the active sub-tab on first visit
  if (viewName === "runs") {
    if (state.runsTab === "expcompare" && !state.expCompareProjects.length) {
      loadExpCompareProjects();
    } else if (state.runsTab === "cellcompare" && !state.cellCompareProjects.length) {
      loadCellCompareProjects();
    } else if (state.runsTab === "compare") {
      renderCompareRunPicker();
    }
  }
}

async function loadOverview() {
  try {
    state.dashboard = await api.getDashboard();
    renderOverview();
  } catch (error) {
    elements.overviewCards.innerHTML = renderEmptyBlock(
      "Overview unavailable",
      error.message,
    );
  }
}

function renderOverview() {
  const dashboard = state.dashboard;
  if (!dashboard) {
    return;
  }

  const cards = [
    {
      label: "Enabled Sources",
      value: dashboard.sources.enabled ?? 0,
      note: `${dashboard.sources.total ?? 0} total monitors`,
    },
    {
      label: "Pending Review",
      value: state.reviewItems.length,
      note: `${dashboard.sources.total ?? 0} monitored source(s)`,
    },
    {
      label: "Active Channels",
      value: dashboard.channels.active ?? 0,
      note: `${dashboard.channels.completed ?? 0} completed`,
    },
    {
      label: "Tracked Runs",
      value: dashboard.runs.active ?? 0,
      note: `${dashboard.runs.completed ?? 0} completed`,
    },
    {
      label: "Open Anomalies",
      value: dashboard.anomalies.active_total ?? 0,
      note: `${dashboard.anomalies.critical ?? 0} critical`,
    },
  ];

  elements.overviewCards.innerHTML = cards
    .map(
      (card) => `
        <article class="metric-card">
          <span class="metric-card-label">${escapeHtml(card.label)}</span>
          <strong class="metric-card-value">${escapeHtml(String(card.value))}</strong>
          <span class="metric-card-note">${escapeHtml(card.note)}</span>
        </article>
      `,
    )
    .join("");

  const activeRuns = dashboard.active_runs || [];
  elements.overviewActiveRuns.innerHTML = activeRuns.length
    ? activeRuns
        .map(
          (run) => `
            <button class="entity-list-button" data-run-id="${run.id}">
              <span class="entity-list-title">Run #${run.id} <em>${escapeHtml(run.status)}</em></span>
              <span class="entity-list-meta">
                Cycle ${run.last_cycle_index ?? "?"} · Retention ${formatPercent(run.capacity_retention_pct)}
              </span>
              <span class="entity-list-meta">${escapeHtml(compactPath(run.source_file_path))}</span>
            </button>
          `,
        )
        .join("")
    : renderEmptyBlock("No active runs", "Start the collector or ingest files to populate this list.");

  const recentAnomalies = dashboard.recent_anomalies || [];
  elements.overviewRecentAnomalies.innerHTML = recentAnomalies.length
    ? recentAnomalies
        .map(
          (anomaly) => `
            <article class="signal-card severity-${escapeHtml(anomaly.severity)}">
              <header>
                <strong>${escapeHtml(anomaly.title)}</strong>
                <span>${escapeHtml(anomaly.severity)}</span>
              </header>
              <p>${escapeHtml(anomaly.description)}</p>
              <small>${formatTimestamp(anomaly.last_seen_at)}</small>
            </article>
          `,
        )
        .join("")
    : renderEmptyBlock("No recent anomalies", "Healthy runs will leave this section quiet.");

  const reports = dashboard.recent_reports || [];
  elements.overviewRecentReports.innerHTML = reports.length
    ? reports
        .map(
          (report) => `
            <article class="signal-card">
              <header>
                <strong>${escapeHtml(report.report_date)}</strong>
                <span>${escapeHtml(report.delivery_status)}</span>
              </header>
              <p>${report.recipient_count} recipient(s)</p>
              <small>${formatTimestamp(report.started_at)}</small>
            </article>
          `,
        )
        .join("")
    : renderEmptyBlock("No reports yet", "Reports will appear here after the reporter worker runs.");
}

async function loadReviewQueue() {
  try {
    state.reviewItems = await api.listMappingReview();
    if (!state.reviewItems.length) {
      state.selectedReviewId = null;
    } else if (!state.reviewItems.some((item) => item.mapping_decision.id === state.selectedReviewId)) {
      state.selectedReviewId = state.reviewItems[0].mapping_decision.id;
    }
    renderReviewQueue();
    renderReviewDetail();
    if (state.dashboard) {
      renderOverview();
    }
  } catch (error) {
    elements.reviewQueueList.innerHTML = renderEmptyBlock(
      "Review queue unavailable",
      error.message,
    );
  }
}

function renderReviewQueue() {
  const items = state.reviewItems;
  if (!items.length) {
    elements.reviewQueueList.innerHTML = "";
    elements.reviewQueueEmpty.hidden = false;
    elements.reviewDetailPanel.classList.add("is-empty");
    return;
  }

  elements.reviewQueueEmpty.hidden = true;
  elements.reviewDetailPanel.classList.remove("is-empty");
  elements.reviewQueueList.innerHTML = items
    .map((item) => {
      const decision = item.mapping_decision;
      const artifact = item.artifact;
      const isSelected = decision.id === state.selectedReviewId;
      return `
        <button class="entity-list-button ${isSelected ? "is-selected" : ""}" data-review-id="${decision.id}">
          <span class="entity-list-title">${escapeHtml(artifact.file_name)}</span>
          <span class="entity-list-meta">
            ${escapeHtml(decision.status)} · confidence ${formatNumber(decision.confidence, 2)}
          </span>
          <span class="entity-list-meta">${escapeHtml(artifact.error_message || decision.review_reason || "Awaiting manual resolution")}</span>
        </button>
      `;
    })
    .join("");
}

function selectReview(mappingDecisionId) {
  state.selectedReviewId = mappingDecisionId;
  renderReviewQueue();
  renderReviewDetail();
}

function renderReviewDetail() {
  const item = getSelectedReviewItem();
  if (!item) {
    elements.reviewItemTitle.textContent = "Nothing selected";
    elements.reviewArtifactMeta.textContent = "Choose a review item from the queue.";
    elements.reviewPayloadJson.textContent = "{}";
    return;
  }

  const { artifact, mapping_decision: decision, latest_ingestion_run: ingestionRun } = item;
  elements.reviewItemTitle.textContent = artifact.file_name;
  elements.reviewArtifactMeta.textContent = [
    `Artifact #${artifact.id}`,
    `source ${artifact.source_id}`,
    `channel ${decision.channel_id ?? "?"}`,
    `status ${decision.status}`,
    ingestionRun ? `last outcome ${ingestionRun.outcome}` : "not yet reprocessed",
  ].join(" · ");
  elements.reviewPayloadJson.textContent = JSON.stringify(item, null, 2);

  elements.reviewResolution.value = "confirmed";
  elements.reviewChannelId.value = decision.channel_id ?? artifact.channel_id ?? "";
  elements.reviewCellId.value = decision.cell_id ?? "";
  elements.reviewCellBuildId.value = decision.cell_build_id ?? "";
  elements.reviewFilePattern.value = "";
  elements.reviewReason.value = decision.review_reason ?? "";
  elements.reviewReprocessNow.checked = true;
}

async function submitReview(forcedResolution) {
  const item = getSelectedReviewItem();
  if (!item) {
    showToast("Choose a review item first.", "warning");
    return;
  }

  const payload = buildReviewPayload(forcedResolution);
  await withButtonBusy(elements.reviewRejectButton, async () => {
    await withFormBusy(elements.reviewResolveForm, async () => {
      const response = await api.resolveMappingReview(item.mapping_decision.id, payload);
      const message =
        payload.resolution === "confirmed"
          ? response.run
            ? `Mapping confirmed and run #${response.run.id} is ready.`
            : "Mapping confirmed."
          : "Mapping review rejected.";
      showToast(message, "success");
      await refreshAll();
      if (response.run?.id) {
        switchView("runs");
        await selectRun(response.run.id);
      }
    });
  });
}

function buildReviewPayload(resolution) {
  const payload = {
    resolution,
    reviewed_by: elements.reviewedBy.value.trim() || "operator",
    review_reason: emptyToNull(elements.reviewReason.value),
    file_pattern: emptyToNull(elements.reviewFilePattern.value),
    reprocess_now: Boolean(elements.reviewReprocessNow.checked),
  };

  const numericFields = [
    ["channel_id", elements.reviewChannelId.value],
    ["cell_id", elements.reviewCellId.value],
    ["cell_build_id", elements.reviewCellBuildId.value],
  ];

  for (const [key, rawValue] of numericFields) {
    if (rawValue.trim()) {
      payload[key] = Number.parseInt(rawValue, 10);
    }
  }

  return payload;
}

function getSelectedReviewItem() {
  return state.reviewItems.find((item) => item.mapping_decision.id === state.selectedReviewId) || null;
}

async function loadRuns() {
  try {
    state.runs = await api.listRuns({ limit: 50 });
    if (!state.runs.length) {
      state.selectedRunId = null;
    } else if (!state.runs.some((run) => run.id === state.selectedRunId)) {
      state.selectedRunId = state.runs[0].id;
      await loadRunContext(state.selectedRunId);
    }
    renderRunsList();
    renderRunDetail();
  } catch (error) {
    elements.runsList.innerHTML = renderEmptyBlock("Runs unavailable", error.message);
  }
}

function renderRunsList() {
  if (!state.runs.length) {
    elements.runsList.innerHTML = renderEmptyBlock(
      "No runs yet",
      "Once live ingestion is active, runs will appear here.",
    );
    return;
  }

  elements.runsList.innerHTML = state.runs
    .map(
      (run) => `
        <button class="entity-list-button ${run.id === state.selectedRunId ? "is-selected" : ""}" data-run-id="${run.id}">
          <span class="entity-list-title">Run #${run.id} <em>${escapeHtml(run.status)}</em></span>
          <span class="entity-list-meta">Cycle ${run.last_cycle_index ?? "?"} · CE ${formatPercent(run.latest_efficiency)}</span>
          <span class="entity-list-meta">${escapeHtml(compactPath(run.source_file_path))}</span>
        </button>
      `,
    )
    .join("");
}

async function selectRun(runId) {
  state.selectedRunId = runId;
  renderRunsList();
  await loadRunContext(runId);
}

async function loadRunContext(runId) {
  elements.runSummaryMeta.textContent = "Loading run detail and provenance";
  if (elements.runSummaryBody) {
    elements.runSummaryBody.innerHTML = '<div class="loading-block">Loading run detail…</div>';
  }
  try {
    const [detailResult, provenanceResult, metricsResult] = await Promise.allSettled([
      api.getRunDetail(runId),
      api.getRunProvenance(runId),
      api.getRunMetrics(runId),
    ]);

    state.runDetail = detailResult.status === "fulfilled" ? detailResult.value : null;
    state.runProvenance = provenanceResult.status === "fulfilled" ? provenanceResult.value : null;
    state.runMetrics = metricsResult.status === "fulfilled" ? metricsResult.value : null;
    renderRunDetail();
    renderRunCharts();
  } catch (error) {
    elements.runSummaryMeta.textContent = "Run detail unavailable";
    if (elements.runSummaryBody) {
      elements.runSummaryBody.innerHTML = renderEmptyBlock("Run detail unavailable", error.message);
    }
  }
}

function renderRunDetail() {
  const detail = state.runDetail;
  if (!detail) {
    elements.runDetailPanel.classList.add("is-empty");
    elements.runSummaryMeta.textContent = "Summary metadata will appear here";
    if (elements.runSummaryBody) {
      elements.runSummaryBody.innerHTML = renderEmptyBlock(
        "Select a run",
        "Choose a run from the list to inspect its summary, metrics, and provenance.",
      );
    }
    elements.runMetricsList.innerHTML = "";
    elements.runProvenanceList.innerHTML = "";
    if (elements.exportRunCycleData) elements.exportRunCycleData.hidden = true;
    return;
  }

  elements.runDetailPanel.classList.remove("is-empty");
  if (elements.exportRunCycleData) {
    elements.exportRunCycleData.hidden = !(detail.cycle_points?.length);
  }
  const summaryRows = [
    ["Run", `#${detail.id}`],
    ["Status", detail.status],
    ["Cycles", detail.last_cycle_index ?? "—"],
    ["Retention", formatPercent(detail.capacity_retention_pct)],
    ["Latest CE", formatPercent(detail.latest_efficiency)],
    ["Parser", detail.parser_type],
    ["Last sampled", formatTimestamp(detail.last_sampled_at)],
    ["Source file", compactPath(detail.source_file_path)],
  ];

  const anomalyCount = detail.anomalies?.length || 0;
  const cyclePreview = (detail.cycle_points || [])
    .slice(-6)
    .map(
      (point) =>
        `C${point.cycle_index}: ${formatNumber(point.discharge_capacity_mah, 3)} mAh / ${formatPercent(point.efficiency)}`,
    )
    .join("\n");

  elements.runSummaryMeta.textContent = `source ${detail.source_id} · channel ${detail.channel_id ?? "?"} · updated ${formatTimestamp(detail.updated_at)}`;
  if (elements.runSummaryBody) {
    elements.runSummaryBody.innerHTML = `
    <div class="summary-grid">
      ${summaryRows
        .map(
          ([label, value]) => `
            <div class="summary-cell">
              <span class="summary-label">${escapeHtml(label)}</span>
              <strong>${escapeHtml(String(value))}</strong>
            </div>
          `,
        )
        .join("")}
    </div>
    <div class="summary-rich-text">
      <h4>Run summary</h4>
      <p>${escapeHtml(
        detail.summary_json?.cell_name
          ? `${detail.summary_json.cell_name} with ${anomalyCount} active anomaly record(s).`
          : `${anomalyCount} anomaly record(s) associated with this run.`,
      )}</p>
      <pre>${escapeHtml(cyclePreview || "No cycle preview available.")}</pre>
    </div>
  `;
  }

  if (state.runMetrics?.run_metrics?.length) {
    elements.runMetricsList.innerHTML = state.runMetrics.run_metrics
      .map(
        (metric) => `
          <article class="metric-row">
            <strong>${escapeHtml(metric.metric_name)}</strong>
            <span>${escapeHtml(formatMetricValue(metric.value_numeric, metric.value_json, metric.unit))}</span>
          </article>
        `,
      )
      .join("");
  } else {
    elements.runMetricsList.innerHTML = renderEmptyBlock(
      "No backend metrics yet",
      "This run has not been materialized into the metrics registry yet.",
    );
  }

  const provenance = state.runProvenance;
  if (!provenance) {
    elements.runProvenanceList.innerHTML = renderEmptyBlock(
      "No provenance available",
      "The provenance endpoint did not return data for this run.",
    );
    return;
  }

  const artifacts = (provenance.artifacts || [])
    .map((artifact) => `<li>${escapeHtml(artifact.file_name)} · ${escapeHtml(artifact.status)} · ${formatTimestamp(artifact.modified_at)}</li>`)
    .join("");
  const mappings = (provenance.mapping_decisions || [])
    .map((decision) => `<li>#${decision.id} · ${escapeHtml(decision.status)} · cell ${decision.cell_id ?? "?"} · build ${decision.cell_build_id ?? "?"}</li>`)
    .join("");
  const ingestions = (provenance.ingestion_runs || [])
    .map((run) => `<li>#${run.id} · ${escapeHtml(run.outcome)} · ${formatTimestamp(run.finished_at || run.started_at)}</li>`)
    .join("");
  const lifecycle = (provenance.lifecycle_events || [])
    .map((event) => `<li>${escapeHtml(event.event_type)} · ${escapeHtml(event.summary)}</li>`)
    .join("");

  elements.runProvenanceList.innerHTML = `
    <section class="detail-stack">
      <article class="detail-card">
        <h4>Artifacts</h4>
        <ul>${artifacts || "<li>No artifacts recorded.</li>"}</ul>
      </article>
      <article class="detail-card">
        <h4>Mapping decisions</h4>
        <ul>${mappings || "<li>No mapping decisions recorded.</li>"}</ul>
      </article>
      <article class="detail-card">
        <h4>Ingestion runs</h4>
        <ul>${ingestions || "<li>No ingestion runs recorded.</li>"}</ul>
      </article>
      <article class="detail-card">
        <h4>Lifecycle events</h4>
        <ul>${lifecycle || "<li>No lifecycle events recorded.</li>"}</ul>
      </article>
    </section>
  `;
}

// =====================================================================
// Metric Registry
// =====================================================================

async function loadMetricDefinitions() {
  elements.metricRegistryList.innerHTML = '<div class="loading-block">Loading metric definitions…</div>';
  try {
    state.metricDefinitions = await api.listMetricDefinitions();
    renderMetricRegistry();
  } catch (error) {
    elements.metricRegistryList.innerHTML = renderEmptyBlock(
      "Metric definitions unavailable",
      error.message,
    );
  }
}

function renderMetricRegistry() {
  const defs = state.metricDefinitions;
  if (!defs.length) {
    elements.metricRegistryList.innerHTML = renderEmptyBlock(
      "No metric definitions",
      "The metrics service has no definitions registered yet.",
    );
    return;
  }

  const filtered = state.metricScopeFilter === "all"
    ? defs
    : defs.filter((d) => d.scope === state.metricScopeFilter);

  if (!filtered.length) {
    elements.metricRegistryList.innerHTML = renderEmptyBlock(
      "No metrics for this scope",
      `No metric definitions with scope "${state.metricScopeFilter}".`,
    );
    return;
  }

  const grouped = {};
  for (const def of filtered) {
    const scope = def.scope || "other";
    if (!grouped[scope]) grouped[scope] = [];
    grouped[scope].push(def);
  }

  const scopeOrder = ["cycle", "run", "cohort", "other"];
  const scopeLabels = { cycle: "Per-cycle", run: "Per-run", cohort: "Per-cohort", other: "Other" };

  let html = "";
  for (const scope of scopeOrder) {
    const items = grouped[scope];
    if (!items) continue;
    html += `<div class="registry-scope-group">
      <h4 class="registry-scope-heading">${escapeHtml(scopeLabels[scope] || scope)}</h4>
      <div class="registry-cards">
        ${items.map((def) => `
          <article class="registry-card">
            <div class="registry-card-header">
              <span class="registry-card-key">${escapeHtml(def.key)}</span>
              <span class="registry-card-unit">${escapeHtml(def.unit || "—")}</span>
            </div>
            <h5 class="registry-card-name">${escapeHtml(def.name)}</h5>
            <p class="registry-card-desc">${escapeHtml(def.description || "No description available.")}</p>
            <div class="registry-card-footer">
              <span class="registry-card-type">${escapeHtml(def.value_type || "numeric")}</span>
              <span class="registry-card-scope">${escapeHtml(def.scope || "—")}</span>
            </div>
          </article>
        `).join("")}
      </div>
    </div>`;
  }

  elements.metricRegistryList.innerHTML = html;
}

// =====================================================================
// Run Comparison
// =====================================================================

function renderCompareRunPicker() {
  if (!elements.compareRunPickerList) return;
  if (!state.runs.length) {
    elements.compareRunPickerList.innerHTML = renderEmptyBlock(
      "No runs available",
      "Once live ingestion is active, runs will appear here for comparison.",
    );
    return;
  }

  elements.compareRunPickerList.innerHTML = state.runs
    .map((run) => {
      const checked = state.compareRunIds.includes(run.id);
      const colorIdx = state.compareRunIds.indexOf(run.id);
      const swatch = checked
        ? `<span class="compare-color-swatch" style="background:${CHART_COLORS[colorIdx % CHART_COLORS.length]}"></span>`
        : "";
      return `
        <button class="compare-run-item${checked ? " is-checked" : ""}" data-compare-run-id="${run.id}" type="button">
          <span class="check-indicator">${checked ? "✓" : ""}</span>
          <div>
            <span class="entity-list-title">${swatch}Run #${run.id} <em>${escapeHtml(run.status)}</em></span>
            <span class="entity-list-meta">Cycle ${run.last_cycle_index ?? "?"} · CE ${formatPercent(run.latest_efficiency)}</span>
            <span class="entity-list-meta">${escapeHtml(compactPath(run.source_file_path))}</span>
          </div>
        </button>
      `;
    })
    .join("");

  updateCompareButton();
}

function toggleCompareRun(runId) {
  const idx = state.compareRunIds.indexOf(runId);
  if (idx >= 0) {
    state.compareRunIds.splice(idx, 1);
  } else if (state.compareRunIds.length < 8) {
    state.compareRunIds.push(runId);
  } else {
    showToast("Maximum 8 runs for comparison.", "warn");
    return;
  }
  renderCompareRunPicker();
}

function updateCompareButton() {
  if (!elements.compareRunsButton) return;
  const n = state.compareRunIds.length;
  elements.compareRunsButton.textContent = `Compare selected (${n})`;
  elements.compareRunsButton.disabled = n < 2;
}

async function loadCompareData() {
  state.compareLoading = true;
  elements.compareSummaryMeta.textContent = `Loading ${state.compareRunIds.length} run details…`;
  elements.compareChartsContainer.innerHTML = '<div class="compare-loading">Loading run data…</div>';
  elements.compareMetricsTable.innerHTML = "";

  const detailPromises = state.compareRunIds.map((id) => api.getRunDetail(id));
  const metricsPromises = state.compareRunIds.map((id) => api.getRunMetrics(id));

  const [detailResults, metricsResults] = await Promise.all([
    Promise.allSettled(detailPromises),
    Promise.allSettled(metricsPromises),
  ]);

  state.compareRunDetails = {};
  state.compareRunMetrics = {};

  state.compareRunIds.forEach((id, i) => {
    if (detailResults[i].status === "fulfilled") {
      state.compareRunDetails[id] = detailResults[i].value;
    }
    if (metricsResults[i].status === "fulfilled") {
      state.compareRunMetrics[id] = metricsResults[i].value;
    }
  });

  state.compareLoading = false;

  const loadedCount = Object.keys(state.compareRunDetails).length;
  elements.compareSummaryMeta.textContent = `${loadedCount} of ${state.compareRunIds.length} runs loaded`;

  renderCompareCharts();
  renderCompareMetricsTable();
}

function getCompareRunLabel(runId) {
  const run = state.runs.find((r) => r.id === runId);
  if (!run) return `Run #${runId}`;
  const path = compactPath(run.source_file_path);
  return path ? `#${runId} ${path}` : `Run #${runId}`;
}

function renderCompareCharts() {
  if (!window.Plotly || !elements.compareChartsContainer) return;
  elements.compareChartsContainer.innerHTML = "";

  const runIds = state.compareRunIds.filter((id) => state.compareRunDetails[id]);
  if (!runIds.length) {
    elements.compareChartsContainer.innerHTML = renderEmptyBlock(
      "No cycle data",
      "None of the selected runs returned cycle point data.",
    );
    return;
  }

  const plotlyLayout = {
    margin: { t: 10, r: 40, b: 100, l: 60 },
    legend: { orientation: "h", y: -0.35 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    xaxis: { automargin: true },
    yaxis: { automargin: true },
  };
  const plotlyConfig = { responsive: true, displayModeBar: "hover", modeBarButtonsToRemove: ["lasso2d", "select2d"] };

  // --- Discharge Capacity chart ---
  const capPanel = createChartPanel("Discharge Capacity");
  elements.compareChartsContainer.append(capPanel);
  const capPlot = capPanel.querySelector(".chart-target");

  const capTraces = runIds.map((id, i) => {
    const points = state.compareRunDetails[id].cycle_points || [];
    return {
      x: points.map((p) => p.cycle_index),
      y: points.map((p) => p.discharge_capacity_mah),
      name: getCompareRunLabel(id),
      mode: "lines+markers",
      type: "scatter",
      line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 },
      marker: { size: 3 },
      hovertemplate: "Cycle %{x}<br>%{y:.2f} mAh<extra>%{fullData.name}</extra>",
    };
  });

  Plotly.newPlot(capPlot, capTraces, {
    ...plotlyLayout,
    xaxis: { title: "Cycle" },
    yaxis: { title: "Capacity (mAh)" },
  }, plotlyConfig);

  // --- Coulombic Efficiency chart ---
  const cePanel = createChartPanel("Coulombic Efficiency");
  elements.compareChartsContainer.append(cePanel);
  const cePlot = cePanel.querySelector(".chart-target");

  const ceTraces = runIds.map((id, i) => {
    const points = state.compareRunDetails[id].cycle_points || [];
    return {
      x: points.map((p) => p.cycle_index),
      y: points.map((p) => (p.efficiency != null ? p.efficiency * 100 : null)),
      name: getCompareRunLabel(id),
      mode: "lines+markers",
      type: "scatter",
      line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 },
      marker: { size: 3 },
      hovertemplate: "Cycle %{x}<br>%{y:.3f}%<extra>%{fullData.name}</extra>",
    };
  });

  Plotly.newPlot(cePlot, ceTraces, {
    ...plotlyLayout,
    xaxis: { title: "Cycle" },
    yaxis: { title: "CE (%)", range: [95, 101] },
  }, plotlyConfig);

  // --- Specific Capacity chart (conditional) ---
  const hasSpecific = runIds.some((id) =>
    (state.compareRunDetails[id].cycle_points || []).some((p) => p.specific_discharge_capacity_mah_g != null)
  );

  if (hasSpecific) {
    const specPanel = createChartPanel("Specific Discharge Capacity");
    elements.compareChartsContainer.append(specPanel);
    const specPlot = specPanel.querySelector(".chart-target");

    const specTraces = runIds.map((id, i) => {
      const points = state.compareRunDetails[id].cycle_points || [];
      return {
        x: points.map((p) => p.cycle_index),
        y: points.map((p) => p.specific_discharge_capacity_mah_g),
        name: getCompareRunLabel(id),
        mode: "lines+markers",
        type: "scatter",
        line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 },
        marker: { size: 3 },
        hovertemplate: "Cycle %{x}<br>%{y:.2f} mAh/g<extra>%{fullData.name}</extra>",
      };
    });

    Plotly.newPlot(specPlot, specTraces, {
      ...plotlyLayout,
      xaxis: { title: "Cycle" },
      yaxis: { title: "Specific Capacity (mAh/g)" },
    }, plotlyConfig);

    requestAnimationFrame(() => Plotly.Plots.resize(specPlot));
  }

  // Deferred resize — Plotly can mis-measure width when the grid layout hasn't settled yet
  requestAnimationFrame(() => {
    Plotly.Plots.resize(capPlot);
    Plotly.Plots.resize(cePlot);
  });
}

function renderCompareMetricsTable() {
  if (!elements.compareMetricsTable) return;

  const runIds = state.compareRunIds.filter((id) => state.compareRunMetrics[id]);
  if (!runIds.length) {
    elements.compareMetricsTable.innerHTML = renderEmptyBlock(
      "No metrics available",
      "None of the selected runs have computed metrics yet.",
    );
    return;
  }

  // Collect union of all metric keys
  const metricMap = new Map();
  for (const id of runIds) {
    const metrics = state.compareRunMetrics[id]?.run_metrics || [];
    for (const m of metrics) {
      if (!metricMap.has(m.metric_key)) {
        metricMap.set(m.metric_key, { name: m.metric_name, unit: m.unit });
      }
    }
  }

  if (!metricMap.size) {
    elements.compareMetricsTable.innerHTML = renderEmptyBlock(
      "No run-level metrics",
      "The selected runs have no computed run-level metrics.",
    );
    return;
  }

  // Build lookup: runId → { metric_key → value }
  const runMetricLookup = {};
  for (const id of runIds) {
    runMetricLookup[id] = {};
    const metrics = state.compareRunMetrics[id]?.run_metrics || [];
    for (const m of metrics) {
      runMetricLookup[id][m.metric_key] = formatMetricValue(m.value_numeric, m.value_json, m.unit);
    }
  }

  const metricKeys = [...metricMap.keys()].sort();

  const headerCells = runIds.map((id, i) => {
    const color = CHART_COLORS[i % CHART_COLORS.length];
    return `<th><span class="compare-color-swatch" style="background:${color}"></span>${escapeHtml(getCompareRunLabel(id))}</th>`;
  }).join("");

  const bodyRows = metricKeys.map((key) => {
    const info = metricMap.get(key);
    const cells = runIds.map((id) =>
      `<td>${escapeHtml(runMetricLookup[id][key] || "—")}</td>`
    ).join("");
    return `<tr><td>${escapeHtml(info.name)}${info.unit ? ` <small>(${escapeHtml(info.unit)})</small>` : ""}</td>${cells}</tr>`;
  }).join("");

  elements.compareMetricsTable.innerHTML = `
    <div class="panel-head" style="margin-top:14px">
      <h3>Metrics comparison</h3>
      <button class="export-button" type="button" data-export="compare-metrics">Export CSV</button>
    </div>
    <div style="overflow-x:auto">
      <table class="compare-metrics-table">
        <thead><tr><th>Metric</th>${headerCells}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    </div>
  `;
}

function exportCompareMetrics() {
  const runIds = state.compareRunIds.filter((id) => state.compareRunMetrics[id]);
  if (!runIds.length) return;

  const metricMap = new Map();
  const runMetricLookup = {};
  for (const id of runIds) {
    runMetricLookup[id] = {};
    const metrics = state.compareRunMetrics[id]?.run_metrics || [];
    for (const m of metrics) {
      if (!metricMap.has(m.metric_key)) metricMap.set(m.metric_key, { name: m.metric_name, unit: m.unit });
      runMetricLookup[id][m.metric_key] = formatMetricValue(m.value_numeric, m.value_json, m.unit);
    }
  }

  const headers = ["Metric", "Unit", ...runIds.map((id) => getCompareRunLabel(id))];
  const rows = [...metricMap.keys()].sort().map((key) => {
    const info = metricMap.get(key);
    return [info.name, info.unit || "", ...runIds.map((id) => runMetricLookup[id][key] || "")];
  });
  downloadCSV("run_comparison_metrics.csv", headers, rows);
  showToast("Metrics comparison exported.", "success");
}

function exportRunCycleData() {
  const detail = state.runDetail;
  if (!detail?.cycle_points?.length) return;

  const headers = ["Cycle", "Discharge capacity (mAh)", "Charge capacity (mAh)", "Coulombic efficiency (%)", "Specific capacity (mAh/g)"];
  const rows = detail.cycle_points.map((p) => [
    p.cycle_index,
    p.discharge_capacity_mah ?? "",
    p.charge_capacity_mah ?? "",
    p.efficiency != null ? (p.efficiency * 100).toFixed(3) : "",
    p.specific_capacity_mah_g ?? "",
  ]);
  const label = detail.summary_json?.cell_name || `run_${detail.id}`;
  downloadCSV(`${label}_cycle_data.csv`, headers, rows);
  showToast("Cycle data exported.", "success");
}

function exportOntologyEntities() {
  const config = ONTOLOGY_TAB_CONFIG[state.ontologyTab];
  if (!config || !state.ontologyEntities.length) return;

  const fieldKeys = config.fields.map((f) => f.key);
  const headers = ["id", ...fieldKeys, "created_at", "updated_at"];
  const rows = state.ontologyEntities.map((e) =>
    [e.id, ...fieldKeys.map((k) => e[k] ?? ""), e.created_at ?? "", e.updated_at ?? ""],
  );
  downloadCSV(`${state.ontologyTab}_export.csv`, headers, rows);
  showToast(`${config.title} exported.`, "success");
}

function exportCellsData() {
  if (!state.currentCells?.length) return;

  const headers = ["Cell name", "Loading (mg/cm²)", "AM %", "Electrolyte", "Separator", "Formation cycles"];
  const rows = state.currentCells.map((c) => [
    c.cell_name ?? "",
    c.loading ?? "",
    c.active_material_pct ?? c.active_material ?? "",
    c.electrolyte ?? "",
    c.separator ?? "",
    c.formation_cycles ?? "",
  ]);
  const expName = state.experimentDetail?.name || "experiment";
  downloadCSV(`${expName}_cells.csv`, headers, rows);
  showToast("Cells data exported.", "success");
}

function clearCompareSelection() {
  state.compareRunIds = [];
  state.compareRunDetails = {};
  state.compareRunMetrics = {};
  state.compareLoading = false;
  renderCompareRunPicker();
  if (elements.compareChartsContainer) elements.compareChartsContainer.innerHTML = "";
  if (elements.compareMetricsTable) elements.compareMetricsTable.innerHTML = "";
  if (elements.compareSummaryMeta) elements.compareSummaryMeta.textContent = "Select runs and click Compare";
}

// =====================================================================
// Ontology Explorer
// =====================================================================

// Cache for relationship picker options (loaded on demand)
const _ontologyPickerCache = {};
async function _loadPickerOptions(key, loaderFn) {
  if (_ontologyPickerCache[key]) return _ontologyPickerCache[key];
  try {
    const items = await loaderFn();
    _ontologyPickerCache[key] = items;
    return items;
  } catch { return []; }
}
function invalidatePickerCache(key) {
  if (key) delete _ontologyPickerCache[key];
  else Object.keys(_ontologyPickerCache).forEach((k) => delete _ontologyPickerCache[k]);
}

const ONTOLOGY_TAB_CONFIG = {
  materials: {
    title: "Materials", subtitle: "Canonical material catalog",
    loader: () => api.listMaterials(), nameKey: "name",
    metaFn: (e) => `${e.category || "—"} · ${e.manufacturer || "unknown"}`,
    endpoint: "materials",
    fields: [
      { key: "name", label: "Name", required: true },
      { key: "category", label: "Category", type: "select", options: ["cathode_active", "anode_active", "binder", "conductive_additive", "electrolyte_salt", "electrolyte_solvent", "electrolyte_additive", "separator", "current_collector", "other"] },
      { key: "manufacturer", label: "Manufacturer" },
      { key: "description", label: "Description", type: "textarea" },
    ],
  },
  materialLots: {
    title: "Material lots", subtitle: "Lot tracking for incoming materials",
    loader: () => api.listMaterialLots(), nameKey: "lot_code",
    metaFn: (e) => `Material #${e.material_id} · ${e.supplier_name || "—"}`,
    endpoint: "material-lots",
    fields: [
      { key: "material_id", label: "Material", type: "async-select", required: true, loader: () => _loadPickerOptions("materials", api.listMaterials), labelFn: (m) => m.name, valueFn: (m) => m.id },
      { key: "lot_code", label: "Lot code", required: true },
      { key: "supplier_name", label: "Supplier" },
      { key: "received_at", label: "Received date", type: "date" },
      { key: "certificate_uri", label: "Certificate URI" },
      { key: "notes", label: "Notes", type: "textarea" },
    ],
  },
  cellBuilds: {
    title: "Cell builds", subtitle: "Physical cell records with traceability",
    loader: () => api.listCellBuilds(), nameKey: "build_name",
    metaFn: (e) => `${e.chemistry || "—"} · ${e.status || "—"} · ${e.form_factor || "—"}`,
    endpoint: "cell-builds",
    fields: [
      { key: "build_name", label: "Build name", required: true },
      { key: "chemistry", label: "Chemistry" },
      { key: "form_factor", label: "Form factor", type: "select", options: ["coin", "pouch", "cylindrical", "prismatic", "other"] },
      { key: "build_date", label: "Build date", type: "date" },
      { key: "status", label: "Status", type: "select", options: ["planned", "built", "testing", "retired", "failed"] },
      { key: "notes", label: "Notes", type: "textarea" },
    ],
  },
  batches: {
    title: "Electrode batches", subtitle: "Batch genealogy and formulation data",
    loader: () => api.listElectrodeBatches(), nameKey: "batch_name",
    metaFn: (e) => `${e.electrode_role || "—"}`,
    endpoint: "electrode-batches",
    fields: [
      { key: "batch_name", label: "Batch name", required: true },
      { key: "electrode_role", label: "Electrode role", type: "select", required: true, options: ["cathode", "anode"] },
      { key: "active_material_id", label: "Active material", type: "async-select", loader: () => _loadPickerOptions("materials", api.listMaterials), labelFn: (m) => `${m.name} (${m.category})`, valueFn: (m) => m.id },
      { key: "process_run_id", label: "Process run", type: "async-select", loader: () => _loadPickerOptions("processRuns", api.listProcessRuns), labelFn: (r) => `${r.name} (${r.process_type})`, valueFn: (r) => r.id },
      { key: "notes", label: "Notes", type: "textarea" },
    ],
  },
  processRuns: {
    title: "Process runs", subtitle: "Manufacturing and test process records",
    loader: () => api.listProcessRuns(), nameKey: "name",
    metaFn: (e) => `${e.process_type || "—"} · ${e.started_at ? e.started_at.slice(0, 10) : "not started"}`,
    endpoint: "process-runs",
    fields: [
      { key: "name", label: "Name", required: true },
      { key: "process_type", label: "Process type", type: "select", options: ["slurry", "coating", "drying", "calendaring", "cutting", "assembly", "electrolyte_fill", "formation", "other"] },
      { key: "protocol_version_id", label: "Protocol", type: "async-select", loader: () => _loadPickerOptions("protocols", api.listProtocolVersions), labelFn: (p) => `${p.name} v${p.version}`, valueFn: (p) => p.id },
      { key: "operator_id", label: "Operator", type: "async-select", loader: () => _loadPickerOptions("operators", api.listOperators), labelFn: (o) => `${o.name} (${o.team || "—"})`, valueFn: (o) => o.id },
      { key: "equipment_asset_id", label: "Equipment", type: "async-select", loader: () => _loadPickerOptions("equipment", api.listEquipmentAssets), labelFn: (eq) => `${eq.name} (${eq.asset_type})`, valueFn: (eq) => eq.id },
      { key: "notes", label: "Notes", type: "textarea" },
    ],
  },
  equipment: {
    title: "Equipment", subtitle: "Lab equipment and cycler assets",
    loader: () => api.listEquipmentAssets(), nameKey: "name",
    metaFn: (e) => `${e.asset_type || "—"} · ${e.vendor || ""} ${e.model || ""}`.trim(),
    endpoint: "equipment-assets",
    fields: [
      { key: "name", label: "Name", required: true },
      { key: "asset_type", label: "Type", type: "select", options: ["cycler", "chamber", "potentiostat", "impedance_analyzer", "dispenser", "coater", "calendar", "fixture", "other"] },
      { key: "vendor", label: "Vendor" },
      { key: "model", label: "Model" },
      { key: "serial_number", label: "Serial number" },
      { key: "location", label: "Location" },
    ],
  },
  protocols: {
    title: "Protocols", subtitle: "Test and process protocol versions",
    loader: () => api.listProtocolVersions(), nameKey: "name",
    metaFn: (e) => `${e.protocol_type || "—"} · v${e.version || "?"}`,
    endpoint: "protocol-versions",
    fields: [
      { key: "name", label: "Name", required: true },
      { key: "version", label: "Version", required: true },
      { key: "protocol_type", label: "Type", type: "select", options: ["formation", "cycling", "rpt", "pulse", "eis", "calendar_aging", "other"] },
      { key: "description", label: "Description", type: "textarea" },
    ],
  },
  people: {
    title: "People", subtitle: "Operators and lab personnel",
    loader: () => api.listOperators(), nameKey: "name",
    metaFn: (e) => `${e.team || "—"} · ${e.email || "—"}`,
    endpoint: "operators",
    fields: [
      { key: "name", label: "Name", required: true },
      { key: "team", label: "Team" },
      { key: "email", label: "Email" },
    ],
  },
  lineage: {
    title: "Lineage edges", subtitle: "Connections between ontology entities",
    loader: () => api.listLineageEdges(), nameKey: "_displayName",
    metaFn: (e) => `${e.relationship_type} · conf ${e.confidence != null ? e.confidence.toFixed(2) : "—"}`,
    endpoint: "lineage-edges",
    // Lineage edges get special list rendering — see renderOntologyEntityList override
    fields: [],
    isLineage: true,
  },
};

async function loadOntologySummary() {
  if (!elements.ontologySummaryBar) return;
  try {
    const summary = await api.getOntologySummary();
    const items = [
      ["Materials", summary.materials],
      ["Lots", summary.material_lots],
      ["Cell builds", summary.cell_builds],
      ["Batches", summary.electrode_batches],
      ["Processes", summary.process_runs],
      ["Equipment", summary.equipment_assets],
      ["Protocols", summary.protocol_versions],
      ["Operators", summary.operators],
      ["Lineage edges", summary.lineage_edges],
    ];
    elements.ontologySummaryBar.innerHTML = items.map(([label, count]) => `
      <div class="kpi-card">
        <span class="kpi-value">${count}</span>
        <span class="kpi-label">${label}</span>
      </div>
    `).join("");
  } catch {
    elements.ontologySummaryBar.innerHTML = "";
  }
}

async function loadOntologyTab(tabName) {
  const config = ONTOLOGY_TAB_CONFIG[tabName];
  if (!config) return;

  elements.ontologyListTitle.textContent = config.title;
  elements.ontologyListSubtitle.textContent = config.subtitle;
  elements.ontologyEntityList.innerHTML = '<div class="loading-block">Loading…</div>';
  elements.ontologyDetailTitle.textContent = "Select an entity";
  elements.ontologyDetailSubtitle.textContent = "Details, lineage, and traceability appear here";
  elements.ontologyDetailBody.innerHTML = '<div class="empty-state">Choose an item from the list.</div>';
  elements.ontologyLineageContainer.innerHTML = "";
  if (elements.ontologyDetailActions) elements.ontologyDetailActions.hidden = true;
  if (elements.ontologyEditFormContainer) {
    elements.ontologyEditFormContainer.hidden = true;
    elements.ontologyEditFormContainer.innerHTML = "";
  }

  // Lineage tab uses a special create form
  if (config.isLineage) {
    renderLineageCreateForm();
  } else {
    renderOntologyCreateForm(config);
  }

  try {
    const raw = await config.loader();
    // Synthesize display name for lineage edges
    if (config.isLineage) {
      state.ontologyEntities = raw.map((e) => ({
        ...e,
        _displayName: `${e.parent_type} #${e.parent_id} → ${e.child_type} #${e.child_id}`,
      }));
    } else {
      state.ontologyEntities = raw;
    }
    renderOntologyEntityList();
  } catch (error) {
    elements.ontologyEntityList.innerHTML = renderEmptyBlock(`${config.title} unavailable`, error.message);
  }
}

function renderOntologyEntityList() {
  const config = ONTOLOGY_TAB_CONFIG[state.ontologyTab];
  if (!config || !state.ontologyEntities.length) {
    elements.ontologyEntityList.innerHTML = renderEmptyBlock(
      `No ${config?.title.toLowerCase() || "entities"}`,
      "No records found in the ontology.",
    );
    return;
  }

  const query = (elements.ontologyFilterInput?.value || "").toLowerCase().trim();
  const filtered = query
    ? state.ontologyEntities.filter((e) => {
        const name = (e[config.nameKey] || "").toLowerCase();
        const meta = config.metaFn(e).toLowerCase();
        return name.includes(query) || meta.includes(query);
      })
    : state.ontologyEntities;

  if (!filtered.length) {
    elements.ontologyEntityList.innerHTML = renderEmptyBlock("No matches", `No ${config.title.toLowerCase()} match "${query}".`);
    return;
  }

  elements.ontologyEntityList.innerHTML = filtered.map((entity) => {
    const isSelected = entity.id === state.ontologySelectedId;
    return `
      <button class="entity-list-button ${isSelected ? "is-selected" : ""}" data-entity-id="${entity.id}">
        <span class="entity-list-title">${escapeHtml(entity[config.nameKey])}</span>
        <span class="entity-list-meta">${escapeHtml(config.metaFn(entity))}</span>
      </button>
    `;
  }).join("");
}

async function selectOntologyEntity(entityId) {
  state.ontologySelectedId = entityId;
  renderOntologyEntityList();

  const entity = state.ontologyEntities.find((e) => e.id === entityId);
  if (!entity) return;

  const config = ONTOLOGY_TAB_CONFIG[state.ontologyTab];
  elements.ontologyDetailTitle.textContent = entity[config.nameKey];
  elements.ontologyDetailSubtitle.textContent = `ID: ${entity.id} · created ${formatTimestamp(entity.created_at)}`;

  // Show edit/delete actions
  if (elements.ontologyDetailActions) elements.ontologyDetailActions.hidden = false;
  if (elements.ontologyEditFormContainer) {
    elements.ontologyEditFormContainer.hidden = true;
    elements.ontologyEditFormContainer.innerHTML = "";
  }

  // Build detail meta grid
  const metaFields = buildOntologyDetailFields(entity);
  elements.ontologyDetailBody.innerHTML = `
    <div class="detail-meta-grid">
      ${metaFields.map(([label, value]) => `
        <div class="detail-meta-item">
          <span class="detail-meta-label">${escapeHtml(label)}</span>
          <span class="detail-meta-value">${escapeHtml(String(value ?? "—"))}</span>
        </div>
      `).join("")}
    </div>
    ${entity.metadata_json ? `<details class="create-form-details"><summary class="create-form-toggle">Metadata JSON</summary><pre style="padding:10px; font-size:0.82rem; overflow-x:auto;">${escapeHtml(JSON.stringify(entity.metadata_json, null, 2))}</pre></details>` : ""}
  `;

  // Resolve FK references for richer display
  if (state.ontologyTab === "materialLots" && entity.material_id) {
    try {
      const mat = await api.getMaterial(entity.material_id);
      if (mat) {
        const matItem = elements.ontologyDetailBody.querySelector('.detail-meta-item');
        if (matItem) {
          const valSpan = matItem.querySelector('.detail-meta-value');
          if (valSpan) valSpan.textContent = `${mat.name} (#${mat.id})`;
        }
      }
    } catch { /* ignore */ }
  }

  // Load lineage for cell builds, batches, and process runs
  elements.ontologyLineageContainer.innerHTML = "";
  if (state.ontologyTab === "cellBuilds") {
    await loadCellBuildLineage(entityId);
  } else if (state.ontologyTab === "batches") {
    await loadBatchLineage(entityId);
  } else if (state.ontologyTab === "processRuns") {
    await loadProcessRunRelationships(entity);
  } else if (state.ontologyTab === "materials") {
    await loadMaterialRelationships(entity);
  }
}

function buildOntologyDetailFields(entity) {
  switch (state.ontologyTab) {
    case "materials":
      return [["Category", entity.category], ["Manufacturer", entity.manufacturer], ["Description", entity.description]];
    case "materialLots":
      return [["Material ID", entity.material_id], ["Lot code", entity.lot_code], ["Supplier", entity.supplier_name], ["Received", entity.received_at], ["Certificate URI", entity.certificate_uri], ["Notes", entity.notes]];
    case "cellBuilds":
      return [["Chemistry", entity.chemistry], ["Form factor", entity.form_factor], ["Status", entity.status], ["Build date", entity.build_date], ["Legacy project", entity.legacy_project_id], ["Legacy experiment", entity.legacy_experiment_id], ["Legacy cell", entity.legacy_cell_id], ["Notes", entity.notes]];
    case "batches":
      return [["Role", entity.electrode_role], ["Active material ID", entity.active_material_id], ["Process run ID", entity.process_run_id], ["Notes", entity.notes],
        ...(entity.formulation_json || []).map((c, i) => [`Component ${i + 1}`, `${c.Component || c.component || "?"}: ${c["Dry Mass Fraction (%)"] ?? c.dry_mass_fraction_pct ?? "?"}%`])];
    case "processRuns":
      return [["Process type", entity.process_type], ["Protocol ID", entity.protocol_version_id], ["Operator ID", entity.operator_id], ["Equipment ID", entity.equipment_asset_id], ["Started", entity.started_at], ["Completed", entity.completed_at], ["Notes", entity.notes]];
    case "equipment":
      return [["Type", entity.asset_type], ["Vendor", entity.vendor], ["Model", entity.model], ["Serial", entity.serial_number], ["Location", entity.location]];
    case "protocols":
      return [["Type", entity.protocol_type], ["Version", entity.version], ["Description", entity.description]];
    case "people":
      return [["Team", entity.team], ["Email", entity.email], ["Active", entity.active ? "Yes" : "No"]];
    case "lineage":
      return [["Parent type", entity.parent_type], ["Parent ID", entity.parent_id], ["Child type", entity.child_type], ["Child ID", entity.child_id], ["Relationship", entity.relationship_type], ["Source", entity.source], ["Confidence", entity.confidence], ["Notes", entity.notes]];
    default:
      return [];
  }
}

// --- Ontology CRUD helpers ---

function buildFormFieldsHTML(fields, values = {}) {
  return fields.map((field) => {
    const val = values[field.key] ?? "";
    const req = field.required ? " required" : "";
    const id = `onto-field-${field.key}`;

    if (field.type === "async-select") {
      // Renders a <select> that will be populated asynchronously after DOM insertion
      return `
        <label class="inline-form-label" for="${id}">${escapeHtml(field.label)}${field.required ? " *" : ""}</label>
        <select id="${id}" name="${field.key}" class="inline-form-input" data-async-select="${field.key}"${req}>
          <option value="">Loading…</option>
        </select>
      `;
    }

    if (field.type === "select") {
      return `
        <label class="inline-form-label" for="${id}">${escapeHtml(field.label)}${field.required ? " *" : ""}</label>
        <select id="${id}" name="${field.key}" class="inline-form-input"${req}>
          <option value="">— select —</option>
          ${field.options.map((opt) => `<option value="${escapeHtml(opt)}"${String(val) === String(opt) ? " selected" : ""}>${escapeHtml(opt)}</option>`).join("")}
        </select>
      `;
    }

    if (field.type === "textarea") {
      return `
        <label class="inline-form-label" for="${id}">${escapeHtml(field.label)}${field.required ? " *" : ""}</label>
        <textarea id="${id}" name="${field.key}" class="inline-form-input" rows="2"${req}>${escapeHtml(String(val))}</textarea>
      `;
    }

    if (field.type === "date") {
      return `
        <label class="inline-form-label" for="${id}">${escapeHtml(field.label)}</label>
        <input id="${id}" name="${field.key}" type="date" class="inline-form-input" value="${escapeHtml(String(val))}" />
      `;
    }

    return `
      <label class="inline-form-label" for="${id}">${escapeHtml(field.label)}${field.required ? " *" : ""}</label>
      <input id="${id}" name="${field.key}" type="text" class="inline-form-input" value="${escapeHtml(String(val))}"${req} />
    `;
  }).join("");
}

/** Populate async-select dropdowns after form HTML is inserted into DOM */
async function hydrateAsyncSelects(containerEl, fields, values = {}) {
  for (const field of fields) {
    if (field.type !== "async-select" || !field.loader) continue;
    const selectEl = containerEl.querySelector(`[data-async-select="${field.key}"]`);
    if (!selectEl) continue;
    try {
      const items = await field.loader();
      const currentVal = String(values[field.key] ?? "");
      selectEl.innerHTML = `<option value="">— select —</option>` +
        items.map((item) => {
          const v = String(field.valueFn(item));
          const label = field.labelFn(item);
          return `<option value="${escapeHtml(v)}"${v === currentVal ? " selected" : ""}>${escapeHtml(label)}</option>`;
        }).join("");
    } catch {
      selectEl.innerHTML = '<option value="">— unavailable —</option>';
    }
  }
}

function collectFormPayload(fields, formEl) {
  const payload = {};
  for (const field of fields) {
    const input = formEl.querySelector(`[name="${field.key}"]`);
    if (!input) continue;
    const val = input.value.trim();
    if (val === "") continue;
    // Convert FK fields to integers
    if (field.type === "async-select" || field.key.endsWith("_id")) {
      const num = Number(val);
      if (!isNaN(num)) { payload[field.key] = num; continue; }
    }
    payload[field.key] = val;
  }
  return payload;
}

function renderOntologyCreateForm(config) {
  if (!elements.ontologyCreateFields || !config.fields) return;
  elements.ontologyCreateFields.innerHTML = buildFormFieldsHTML(config.fields);
  if (elements.ontologyCreateDetails) elements.ontologyCreateDetails.open = false;
  // Hydrate async selects
  hydrateAsyncSelects(elements.ontologyCreateFields, config.fields);
}

async function submitOntologyCreate() {
  const config = ONTOLOGY_TAB_CONFIG[state.ontologyTab];
  if (!config?.endpoint) return;

  const payload = collectFormPayload(config.fields, elements.ontologyCreateForm);
  if (!payload[config.fields.find((f) => f.required)?.key]) {
    showToast("Please fill in required fields.", "warn");
    return;
  }

  try {
    await api.createOntologyEntity(config.endpoint, payload);
    showToast(`${config.title.replace(/s$/, "")} created.`, "success");
    elements.ontologyCreateForm.reset();
    if (elements.ontologyCreateDetails) elements.ontologyCreateDetails.open = false;
    invalidatePickerCache();
    await loadOntologyTab(state.ontologyTab);
    loadOntologySummary();
  } catch (error) {
    showToast(`Create failed: ${error.message}`, "error");
  }
}

function showOntologyEditForm() {
  const config = ONTOLOGY_TAB_CONFIG[state.ontologyTab];
  const entity = state.ontologyEntities.find((e) => e.id === state.ontologySelectedId);
  if (!config?.fields || !entity || !elements.ontologyEditFormContainer) return;

  elements.ontologyEditFormContainer.hidden = false;
  elements.ontologyDetailBody.hidden = true;

  elements.ontologyEditFormContainer.innerHTML = `
    <form id="ontologyEditForm" class="inline-form">
      ${buildFormFieldsHTML(config.fields, entity)}
      <div class="form-actions">
        <button class="primary-button" type="submit">Save</button>
        <button class="secondary-button" type="button" id="ontologyEditCancel">Cancel</button>
      </div>
    </form>
  `;

  // Hydrate async selects with current values
  hydrateAsyncSelects(elements.ontologyEditFormContainer, config.fields, entity);

  const editForm = document.getElementById("ontologyEditForm");
  editForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitOntologyEdit(editForm);
  });

  document.getElementById("ontologyEditCancel")?.addEventListener("click", () => {
    elements.ontologyEditFormContainer.hidden = true;
    elements.ontologyEditFormContainer.innerHTML = "";
    elements.ontologyDetailBody.hidden = false;
  });
}

async function submitOntologyEdit(formEl) {
  const config = ONTOLOGY_TAB_CONFIG[state.ontologyTab];
  if (!config?.endpoint || !state.ontologySelectedId) return;

  const payload = collectFormPayload(config.fields, formEl);

  try {
    await api.updateOntologyEntity(config.endpoint, state.ontologySelectedId, payload);
    showToast(`${config.title.replace(/s$/, "")} updated.`, "success");
    elements.ontologyEditFormContainer.hidden = true;
    elements.ontologyEditFormContainer.innerHTML = "";
    elements.ontologyDetailBody.hidden = false;
    invalidatePickerCache();
    await loadOntologyTab(state.ontologyTab);
    await selectOntologyEntity(state.ontologySelectedId);
    loadOntologySummary();
  } catch (error) {
    showToast(`Update failed: ${error.message}`, "error");
  }
}

async function deleteOntologyEntity() {
  const config = ONTOLOGY_TAB_CONFIG[state.ontologyTab];
  const entity = state.ontologyEntities.find((e) => e.id === state.ontologySelectedId);
  if (!config?.endpoint || !entity) return;

  const name = entity[config.nameKey] || `#${entity.id}`;
  if (!window.confirm(`Delete ${config.title.replace(/s$/, "").toLowerCase()} "${name}"? This cannot be undone.`)) return;

  try {
    await api.deleteOntologyEntity(config.endpoint, state.ontologySelectedId);
    showToast(`${name} deleted.`, "success");
    state.ontologySelectedId = null;
    invalidatePickerCache();
    await loadOntologyTab(state.ontologyTab);
    loadOntologySummary();
  } catch (error) {
    showToast(`Delete failed: ${error.message}`, "error");
  }
}

async function loadCellBuildLineage(cellBuildId) {
  elements.ontologyLineageContainer.innerHTML = '<div class="loading-block">Loading lineage…</div>';
  try {
    const lineage = await api.getCellBuildLineage(cellBuildId);
    renderCellBuildLineage(lineage);
  } catch (error) {
    elements.ontologyLineageContainer.innerHTML = renderEmptyBlock("Lineage unavailable", error.message);
  }
}

function renderCellBuildLineage(lineage) {
  const sections = [];

  if (lineage.source_batches?.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Source electrode batches</h4>
        ${lineage.source_batches.map((b) => `
          <div class="lineage-card">
            <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--batch">Batch</span> ${escapeHtml(b.batch_name)}</span>
            <span class="lineage-card-meta">${escapeHtml(b.electrode_role || "—")} · ID: ${b.id}</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  if (lineage.source_materials?.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Source materials</h4>
        ${lineage.source_materials.map((m) => `
          <div class="lineage-card">
            <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--material">Material</span> ${escapeHtml(m.name)}</span>
            <span class="lineage-card-meta">${escapeHtml(m.category || "—")} · ${escapeHtml(m.manufacturer || "—")}</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  if (lineage.related_legacy_experiments?.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Legacy experiments</h4>
        ${lineage.related_legacy_experiments.map((e) => `
          <div class="lineage-card">
            <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--legacy">Legacy</span> ${escapeHtml(e.experiment_name || `Experiment #${e.legacy_experiment_id}`)}</span>
            <span class="lineage-card-meta">Project: ${escapeHtml(e.project_name || "—")} · ID: ${e.legacy_experiment_id}</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  if (lineage.lineage_edges?.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Lineage edges (${lineage.lineage_edges.length})</h4>
        ${lineage.lineage_edges.map((edge) => `
          <div class="lineage-card">
            <span class="lineage-card-title">${escapeHtml(edge.parent_type)} #${edge.parent_id} → ${escapeHtml(edge.child_type)} #${edge.child_id}</span>
            <span class="lineage-card-meta">${escapeHtml(edge.relationship_type)} · confidence ${edge.confidence != null ? formatNumber(edge.confidence, 2) : "—"} · ${escapeHtml(edge.source || "—")}</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  elements.ontologyLineageContainer.innerHTML = sections.length
    ? sections.join("")
    : renderEmptyBlock("No lineage", "No lineage edges found for this cell build.");
}

async function loadBatchLineage(batchId) {
  elements.ontologyLineageContainer.innerHTML = '<div class="loading-block">Loading lineage…</div>';
  try {
    const [lineage, descendants] = await Promise.all([
      api.getBatchLineage(batchId),
      api.getBatchDescendants(batchId),
    ]);
    renderBatchLineage(lineage, descendants);
  } catch (error) {
    elements.ontologyLineageContainer.innerHTML = renderEmptyBlock("Lineage unavailable", error.message);
  }
}

function renderBatchLineage(lineage, descendants) {
  const sections = [];

  if (lineage.active_material) {
    const m = lineage.active_material;
    sections.push(`
      <div class="lineage-section">
        <h4>Active material</h4>
        <div class="lineage-card">
          <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--material">Material</span> ${escapeHtml(m.name)}</span>
          <span class="lineage-card-meta">${escapeHtml(m.category || "—")} · ${escapeHtml(m.manufacturer || "—")}</span>
        </div>
      </div>
    `);
  }

  if (lineage.formulation_materials?.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Formulation materials</h4>
        ${lineage.formulation_materials.map((m) => `
          <div class="lineage-card">
            <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--material">Material</span> ${escapeHtml(m.name)}</span>
            <span class="lineage-card-meta">${escapeHtml(m.category || "—")} · ${escapeHtml(m.manufacturer || "—")}</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  if (lineage.cell_builds?.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Cell builds (${lineage.cell_builds.length})</h4>
        ${lineage.cell_builds.map((cb) => `
          <div class="lineage-card">
            <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--build">Build</span> ${escapeHtml(cb.build_name)}</span>
            <span class="lineage-card-meta">${escapeHtml(cb.chemistry || "—")} · ${escapeHtml(cb.status || "—")}</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  if (lineage.parent_batches?.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Parent batches</h4>
        ${lineage.parent_batches.map((b) => `
          <div class="lineage-card">
            <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--batch">Parent</span> ${escapeHtml(b.batch_name)}</span>
            <span class="lineage-card-meta">${escapeHtml(b.electrode_role || "—")}</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  if (lineage.child_batches?.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Child batches</h4>
        ${lineage.child_batches.map((b) => `
          <div class="lineage-card">
            <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--batch">Child</span> ${escapeHtml(b.batch_name)}</span>
            <span class="lineage-card-meta">${escapeHtml(b.electrode_role || "—")}</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  const descList = descendants?.descendants || [];
  if (descList.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Descendants (${descList.length})</h4>
        ${descList.map((d) => `
          <div class="lineage-card">
            <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--batch">Depth ${d.depth}</span> ${escapeHtml(d.batch.batch_name)}</span>
            <span class="lineage-card-meta">${d.cell_build_count} cell builds · ${d.legacy_experiment_count} legacy experiments</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  if (lineage.legacy_experiments?.length) {
    sections.push(`
      <div class="lineage-section">
        <h4>Legacy experiments</h4>
        ${lineage.legacy_experiments.map((e) => `
          <div class="lineage-card">
            <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--legacy">Legacy</span> ${escapeHtml(e.experiment_name || `Experiment #${e.legacy_experiment_id}`)}</span>
            <span class="lineage-card-meta">Project: ${escapeHtml(e.project_name || "—")}</span>
          </div>
        `).join("")}
      </div>
    `);
  }

  elements.ontologyLineageContainer.innerHTML = sections.length
    ? sections.join("")
    : renderEmptyBlock("No lineage", "No lineage data found for this batch.");
}

// --- Process run & material relationship views ---

async function loadProcessRunRelationships(entity) {
  const sections = [];
  try {
    if (entity.protocol_version_id) {
      const protocols = await _loadPickerOptions("protocols", api.listProtocolVersions);
      const proto = protocols.find((p) => p.id === entity.protocol_version_id);
      if (proto) {
        sections.push(`<div class="lineage-section"><h4>Protocol</h4><div class="lineage-card">
          <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--material">Protocol</span> ${escapeHtml(proto.name)} v${escapeHtml(proto.version)}</span>
          <span class="lineage-card-meta">${escapeHtml(proto.protocol_type || "—")}</span>
        </div></div>`);
      }
    }
    if (entity.operator_id) {
      const operators = await _loadPickerOptions("operators", api.listOperators);
      const op = operators.find((o) => o.id === entity.operator_id);
      if (op) {
        sections.push(`<div class="lineage-section"><h4>Operator</h4><div class="lineage-card">
          <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--build">Operator</span> ${escapeHtml(op.name)}</span>
          <span class="lineage-card-meta">${escapeHtml(op.team || "—")} · ${escapeHtml(op.email || "—")}</span>
        </div></div>`);
      }
    }
    if (entity.equipment_asset_id) {
      const equipment = await _loadPickerOptions("equipment", api.listEquipmentAssets);
      const eq = equipment.find((e) => e.id === entity.equipment_asset_id);
      if (eq) {
        sections.push(`<div class="lineage-section"><h4>Equipment</h4><div class="lineage-card">
          <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--batch">Equipment</span> ${escapeHtml(eq.name)}</span>
          <span class="lineage-card-meta">${escapeHtml(eq.asset_type || "—")} · ${escapeHtml(eq.vendor || "")} ${escapeHtml(eq.model || "")}</span>
        </div></div>`);
      }
    }
    if (entity.settings_json) {
      sections.push(`<div class="lineage-section"><h4>Process settings</h4>
        <pre style="padding:10px; font-size:0.82rem; overflow-x:auto; background:var(--surface-alt); border-radius:6px;">${escapeHtml(JSON.stringify(entity.settings_json, null, 2))}</pre>
      </div>`);
    }
  } catch { /* ignore */ }
  elements.ontologyLineageContainer.innerHTML = sections.length
    ? sections.join("")
    : renderEmptyBlock("No relationships", "No linked entities found for this process run.");
}

async function loadMaterialRelationships(entity) {
  const sections = [];
  try {
    // Show lots for this material
    const allLots = await _loadPickerOptions("materialLots", api.listMaterialLots);
    const lots = allLots.filter((l) => l.material_id === entity.id);
    if (lots.length) {
      sections.push(`<div class="lineage-section"><h4>Material lots (${lots.length})</h4>
        ${lots.map((l) => `<div class="lineage-card">
          <span class="lineage-card-title"><span class="lineage-edge-badge lineage-edge-badge--batch">Lot</span> ${escapeHtml(l.lot_code)}</span>
          <span class="lineage-card-meta">${escapeHtml(l.supplier_name || "—")} · received ${l.received_at || "—"}</span>
        </div>`).join("")}
      </div>`);
    }
    // Show lineage edges involving this material
    const edges = await api.listLineageEdges({ parentType: "material", parentId: entity.id });
    if (edges.length) {
      sections.push(`<div class="lineage-section"><h4>Outgoing lineage (${edges.length})</h4>
        ${edges.map((edge) => `<div class="lineage-card">
          <span class="lineage-card-title">${escapeHtml(edge.relationship_type)} → ${escapeHtml(edge.child_type)} #${edge.child_id}</span>
          <span class="lineage-card-meta">confidence ${edge.confidence != null ? edge.confidence.toFixed(2) : "—"} · ${escapeHtml(edge.source || "—")}</span>
        </div>`).join("")}
      </div>`);
    }
  } catch { /* ignore */ }
  elements.ontologyLineageContainer.innerHTML = sections.length
    ? sections.join("")
    : renderEmptyBlock("No relationships", "No lots or lineage edges found for this material.");
}

// --- Lineage edge creation form ---

function renderLineageCreateForm() {
  if (!elements.ontologyCreateFields) return;
  const entityTypes = ["material", "material_lot", "electrode_batch", "protocol_version", "operator", "fixture", "equipment_asset", "process_run", "cell_build", "project", "experiment", "cell", "test_run"];
  const typeOptions = entityTypes.map((t) => `<option value="${t}">${t}</option>`).join("");
  elements.ontologyCreateFields.innerHTML = `
    <label class="inline-form-label" for="le-parent-type">Parent type *</label>
    <select id="le-parent-type" name="parent_type" class="inline-form-input" required>${typeOptions}</select>
    <label class="inline-form-label" for="le-parent-id">Parent ID *</label>
    <input id="le-parent-id" name="parent_id" type="number" min="1" class="inline-form-input" required />
    <label class="inline-form-label" for="le-child-type">Child type *</label>
    <select id="le-child-type" name="child_type" class="inline-form-input" required>${typeOptions}</select>
    <label class="inline-form-label" for="le-child-id">Child ID *</label>
    <input id="le-child-id" name="child_id" type="number" min="1" class="inline-form-input" required />
    <label class="inline-form-label" for="le-rel-type">Relationship *</label>
    <input id="le-rel-type" name="relationship_type" type="text" class="inline-form-input" required placeholder="e.g. feeds_batch, built_into" />
    <label class="inline-form-label" for="le-source">Source</label>
    <input id="le-source" name="source" type="text" class="inline-form-input" placeholder="e.g. manual, import" />
    <label class="inline-form-label" for="le-confidence">Confidence (0-1)</label>
    <input id="le-confidence" name="confidence" type="number" min="0" max="1" step="0.01" class="inline-form-input" />
    <label class="inline-form-label" for="le-notes">Notes</label>
    <textarea id="le-notes" name="notes" class="inline-form-input" rows="2"></textarea>
  `;
  if (elements.ontologyCreateDetails) elements.ontologyCreateDetails.open = false;
}

// --- Lineage edge CRUD ---

async function submitLineageEdgeCreate() {
  const formEl = elements.ontologyCreateForm;
  if (!formEl) return;
  const payload = {};
  for (const input of formEl.querySelectorAll("[name]")) {
    const val = input.value.trim();
    if (!val) continue;
    if (input.name === "parent_id" || input.name === "child_id") {
      payload[input.name] = Number(val);
    } else if (input.name === "confidence") {
      payload[input.name] = parseFloat(val);
    } else {
      payload[input.name] = val;
    }
  }
  if (!payload.parent_type || !payload.parent_id || !payload.child_type || !payload.child_id || !payload.relationship_type) {
    showToast("Please fill in all required fields.", "warn");
    return;
  }
  try {
    await api.createLineageEdge(payload);
    showToast("Lineage edge created.", "success");
    formEl.reset();
    if (elements.ontologyCreateDetails) elements.ontologyCreateDetails.open = false;
    invalidatePickerCache();
    await loadOntologyTab("lineage");
    loadOntologySummary();
  } catch (error) {
    showToast(`Create failed: ${error.message}`, "error");
  }
}

async function deleteLineageEdge() {
  const entity = state.ontologyEntities.find((e) => e.id === state.ontologySelectedId);
  if (!entity) return;
  if (!window.confirm(`Delete lineage edge #${entity.id}? This cannot be undone.`)) return;
  try {
    await api.deleteLineageEdge(entity.id);
    showToast("Lineage edge deleted.", "success");
    state.ontologySelectedId = null;
    await loadOntologyTab("lineage");
    loadOntologySummary();
  } catch (error) {
    showToast(`Delete failed: ${error.message}`, "error");
  }
}

// --- Ontology global search ---

let _globalSearchTimeout = null;
async function handleOntologyGlobalSearch(query) {
  if (!query || query.length < 2) {
    // Reset to current tab
    renderOntologyEntityList();
    return;
  }
  elements.ontologyEntityList.innerHTML = '<div class="loading-block">Searching…</div>';
  try {
    const results = await api.searchOntology(query);
    if (!results.length) {
      elements.ontologyEntityList.innerHTML = renderEmptyBlock("No results", `No ontology entities match "${query}".`);
      return;
    }
    elements.ontologyEntityList.innerHTML = results.map((r) => `
      <button class="entity-list-button" data-search-entity-type="${r.entity_type}" data-search-entity-id="${r.entity_id}">
        <span class="entity-list-title">${escapeHtml(r.name)}</span>
        <span class="entity-list-meta">${escapeHtml(r.entity_type)} · ${escapeHtml(r.detail || "")}</span>
      </button>
    `).join("");
  } catch (error) {
    elements.ontologyEntityList.innerHTML = renderEmptyBlock("Search error", error.message);
  }
}

// =====================================================================
// Projects & Experiments
// =====================================================================

async function loadProjects() {
  try {
    state.projects = await api.listProjects();
    renderProjectsList();
  } catch (error) {
    elements.projectsList.innerHTML = renderEmptyBlock("Projects unavailable", error.message);
  }
}

function updateFinderBreadcrumb(projectName, experimentName) {
  if (!elements.finderBreadcrumb) return;
  let html = `<span class="finder-breadcrumb-segment ${projectName ? "is-clickable" : "is-active"}" data-breadcrumb="root">All Projects</span>`;
  if (projectName) {
    html += `<span class="finder-breadcrumb-sep">&#x203A;</span>`;
    html += `<span class="finder-breadcrumb-segment ${experimentName ? "is-clickable" : "is-active"}" data-breadcrumb="project">${escapeHtml(projectName)}</span>`;
  }
  if (experimentName) {
    html += `<span class="finder-breadcrumb-sep">&#x203A;</span>`;
    html += `<span class="finder-breadcrumb-segment is-active" data-breadcrumb="experiment">${escapeHtml(experimentName)}</span>`;
  }
  elements.finderBreadcrumb.innerHTML = html;
}

function renderProjectsList() {
  if (!state.projects.length) {
    elements.projectsList.innerHTML = renderEmptyBlock(
      "No projects yet",
      "Create your first project using the form below.",
    );
    return;
  }

  const query = (elements.projectSearchInput?.value || "").toLowerCase().trim();
  const filtered = query
    ? state.projects.filter((p) =>
        (p.name || "").toLowerCase().includes(query) ||
        (p.project_type || "").toLowerCase().includes(query) ||
        (p.description || "").toLowerCase().includes(query))
    : state.projects;

  if (!filtered.length) {
    elements.projectsList.innerHTML = renderEmptyBlock("No matches", `No projects match "${query}".`);
    return;
  }

  elements.projectsList.innerHTML = filtered
    .map((project) => {
      const isSelected = project.id === state.selectedProjectId;
      const badgeClass = typeBadgeClass(project.project_type);
      const count = project.experiment_count ?? 0;
      return `
        <button class="finder-item ${isSelected ? "is-selected" : ""}" data-project-id="${project.id}">
          <span class="finder-item-content">
            <span class="finder-item-name">
              ${escapeHtml(project.name)}
              <span class="type-badge ${badgeClass}">${escapeHtml(project.project_type)}</span>
            </span>
            <span class="finder-item-meta">${count} exp</span>
          </span>
          <span class="finder-item-actions">
            <span class="finder-action-btn" data-rename-project="${project.id}" title="Rename">&#9998;</span>
            <span class="finder-action-btn finder-action-btn--danger" data-delete-project="${project.id}" title="Delete">&times;</span>
          </span>
          <span class="finder-item-chevron">&#x203A;</span>
        </button>
      `;
    })
    .join("");
}

function typeBadgeClass(projectType) {
  switch (projectType) {
    case "Cathode": return "type-badge--cathode";
    case "Anode": return "type-badge--anode";
    case "Full Cell": return "type-badge--full-cell";
    default: return "";
  }
}

async function selectProject(projectId) {
  state.selectedProjectId = projectId;
  state.selectedExperimentId = null;
  state.experimentDetail = null;

  // Clear stale experiments immediately so switching projects never shows old data
  state.experiments = [];
  renderProjectsList();

  // Show experiments column, hide detail column
  elements.finderColExperiments?.classList.remove("finder-col--hidden");
  elements.finderColDetail?.classList.add("finder-col--hidden");

  elements.projectDetailTitle.textContent = "Loading…";
  elements.projectDetailMeta.textContent = "";
  elements.experimentsList.innerHTML = '<div class="loading-block">Loading experiments…</div>';

  try {
    const project = await api.getProject(projectId);
    elements.projectDetailTitle.textContent = project.name;
    elements.projectDetailMeta.textContent = `${project.project_type} · ${project.experiment_count ?? 0} experiments · ${project.cell_count ?? 0} cells`;

    elements.projectDetailBody.innerHTML = project.description
      ? `<div class="detail-card"><p>${escapeHtml(project.description)}</p></div>`
      : "";

    updateFinderBreadcrumb(project.name, null);
    elements.createExperimentDetails.hidden = false;
  } catch (error) {
    elements.projectDetailTitle.textContent = "Error";
    elements.projectDetailMeta.textContent = error.message;
  }

  // Always load experiments regardless of whether getProject succeeded
  await loadExperiments(projectId);
}

async function loadExperiments(projectId) {
  try {
    const experiments = await api.listExperiments(projectId);
    // Guard against stale responses when user switched projects before this completed
    if (state.selectedProjectId !== projectId) return;
    state.experiments = experiments;
    renderExperimentsList();
  } catch (error) {
    if (state.selectedProjectId !== projectId) return;
    elements.experimentsList.innerHTML = renderEmptyBlock("Experiments unavailable", error.message);
  }
}

function renderExperimentsList() {
  if (!state.experiments.length) {
    elements.experimentsList.innerHTML = renderEmptyBlock(
      "No experiments",
      "Add your first experiment using the form below.",
    );
    return;
  }

  const query = (elements.experimentSearchInput?.value || "").toLowerCase().trim();
  const filtered = query
    ? state.experiments.filter((exp) => {
        const name = (exp.name || exp.cell_name || "").toLowerCase();
        const date = (exp.experiment_date || exp.created_date || "").toLowerCase();
        return name.includes(query) || date.includes(query);
      })
    : state.experiments;

  if (!filtered.length) {
    elements.experimentsList.innerHTML = renderEmptyBlock("No matches", `No experiments match "${query}".`);
    return;
  }

  elements.experimentsList.innerHTML = filtered
    .map((exp) => {
      const isSelected = exp.id === state.selectedExperimentId;
      const name = exp.name || exp.cell_name || `Experiment #${exp.id}`;
      const cellCount = exp.cell_count ?? "";
      const date = exp.experiment_date || exp.created_date || "";
      return `
        <button class="finder-item ${isSelected ? "is-selected" : ""}" data-experiment-id="${exp.id}">
          <span class="finder-item-content">
            <span class="finder-item-name">${escapeHtml(name)}</span>
            <span class="finder-item-meta">${cellCount ? cellCount + " cells · " : ""}${date}</span>
          </span>
          <span class="finder-item-actions">
            <span class="finder-action-btn" data-rename-experiment="${exp.id}" title="Rename">&#9998;</span>
            <span class="finder-action-btn finder-action-btn--danger" data-delete-experiment="${exp.id}" title="Delete">&times;</span>
          </span>
          <span class="finder-item-chevron">&#x203A;</span>
        </button>
      `;
    })
    .join("");
}

async function selectExperiment(experimentId) {
  state.selectedExperimentId = experimentId;
  renderExperimentsList();

  // Show the detail column
  elements.finderColDetail?.classList.remove("finder-col--hidden");

  elements.cellsSectionTitle.textContent = "Loading cells…";
  elements.cellsSectionMeta.textContent = "";
  elements.cellsTableContainer.innerHTML = '<div class="loading-block">Loading…</div>';
  if (elements.experimentChartsContainer) elements.experimentChartsContainer.innerHTML = "";
  if (elements.experimentStatsPanel) elements.experimentStatsPanel.hidden = true;

  let cells = [];
  try {
    const experiment = await api.getExperiment(experimentId);
    // Guard against stale responses when user clicked another experiment before this completed
    if (state.selectedExperimentId !== experimentId) return;
    state.experimentDetail = experiment;

    const expName = experiment.name || experiment.cell_name || `Experiment #${experiment.id}`;

    // Parse legacy data_json if present
    cells = experiment.cells || [];
    let notes = experiment.notes || experiment.experiment_notes || "";
    let discDiameter = experiment.disc_diameter_mm;

    if (!cells.length && experiment.data_json) {
      try {
        const parsed = typeof experiment.data_json === "string"
          ? JSON.parse(experiment.data_json)
          : experiment.data_json;
        cells = parsed.cells || [];
        discDiameter = discDiameter || parsed.disc_diameter_mm;
        notes = notes || parsed.experiment_notes || "";
      } catch (_) { /* ignore parse errors */ }
    }

    elements.cellsSectionTitle.textContent = `Cells — ${expName}`;
    elements.cellsSectionMeta.textContent = [
      discDiameter ? `${discDiameter}mm disc` : null,
      experiment.electrolyte,
      notes,
    ].filter(Boolean).join(" · ");

    // Update breadcrumb with experiment name
    const projName = elements.projectDetailTitle?.textContent || "Project";
    updateFinderBreadcrumb(projName, expName);

    state.currentCells = cells;
    renderCellsTable(cells);
    if (elements.cellDetailPanel) elements.cellDetailPanel.hidden = true;
  } catch (error) {
    elements.cellsTableContainer.innerHTML = renderEmptyBlock("Cells unavailable", error.message);
    return;
  }

  // Chart and stats rendering are independent of cell table — errors here must not overwrite it
  try {
    renderExperimentCharts(cells);
  } catch (chartError) {
    console.warn("Experiment chart rendering failed:", chartError);
  }
  try {
    renderExperimentStats(cells);
  } catch (statsError) {
    console.warn("Experiment stats rendering failed:", statsError);
  }
}

function renderCellsTable(cells) {
  if (!cells.length) {
    elements.cellsTableContainer.innerHTML = renderEmptyBlock(
      "No cells",
      "Add cells using the form below.",
    );
    return;
  }

  const rows = cells.map((cell, idx) => {
    const am = cell.active_material_pct ?? cell.active_material;
    const formulation = cell.formulation || [];
    const formulationStr = formulation.length
      ? formulation.map((c) => `${c.Component || c.component} ${c["Dry Mass Fraction (%)"] ?? c.dry_mass_fraction_pct ?? ""}%`).join(", ")
      : "—";
    const hasCycling = Boolean(cell.data_json);
    const dataIcon = hasCycling ? '<span class="cell-data-badge" title="Has cycling data">&#x2713;</span>' : '';
    return `
      <tr data-cell-index="${idx}" class="${hasCycling ? "clickable-row" : ""}" title="${hasCycling ? "Click to view cycling data" : ""}">
        <td>${escapeHtml(cell.cell_name)} ${dataIcon}</td>
        <td>${cell.loading != null ? formatNumber(cell.loading, 2) : "—"}</td>
        <td>${am != null ? formatNumber(am, 1) + "%" : "—"}</td>
        <td>${escapeHtml(cell.electrolyte || "—")}</td>
        <td>${escapeHtml(cell.separator || "—")}</td>
        <td>${cell.formation_cycles ?? "—"}</td>
        <td title="${escapeHtml(formulationStr)}">${formulation.length ? formulation.length + " components" : "—"}</td>
        <td class="cell-actions-col">
          <span class="cell-action-btn" data-upload-cell="${cell.id}" title="Upload cycling data">&#x21E7;</span>
          <span class="cell-action-btn" data-edit-cell="${cell.id}" title="Edit">&#9998;</span>
          <span class="cell-action-btn cell-action-btn--danger" data-delete-cell="${cell.id}" title="Delete">&times;</span>
        </td>
      </tr>
    `;
  }).join("");

  elements.cellsTableContainer.innerHTML = `
    <div class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Cell</th>
            <th>Loading</th>
            <th>AM %</th>
            <th>Electrolyte</th>
            <th>Separator</th>
            <th>Form. cycles</th>
            <th>Formulation</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

// =====================================================================
// Cell Detail Drilldown
// =====================================================================

function showCellEditModal(cell) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="modal-dialog">
      <div class="modal-header">
        <h3>Edit Cell</h3>
        <button class="close-button" type="button" data-modal-close>&times;</button>
      </div>
      <form class="form-stack form-stack--compact modal-body">
        <div class="field-row">
          <label class="field"><span>Cell name</span>
            <input name="cell_name" type="text" value="${escapeHtml(cell.cell_name || "")}" required />
          </label>
          <label class="field"><span>Loading (mg/cm²)</span>
            <input name="loading" type="number" step="0.01" value="${cell.loading ?? ""}" />
          </label>
          <label class="field"><span>AM %</span>
            <input name="active_material_pct" type="number" step="0.1" value="${cell.active_material_pct ?? ""}" />
          </label>
        </div>
        <div class="field-row">
          <label class="field"><span>Electrolyte</span>
            <input name="electrolyte" type="text" value="${escapeHtml(cell.electrolyte || "")}" />
          </label>
          <label class="field"><span>Separator</span>
            <input name="separator" type="text" value="${escapeHtml(cell.separator || "")}" />
          </label>
          <label class="field"><span>Formation cycles</span>
            <input name="formation_cycles" type="number" min="0" max="50" value="${cell.formation_cycles ?? 4}" />
          </label>
        </div>
        <div class="field-row">
          <label class="field"><span>Group</span>
            <input name="group_assignment" type="text" value="${escapeHtml(cell.group_assignment || "")}" />
          </label>
          <label class="field"><span>Test number</span>
            <input name="test_number" type="text" value="${escapeHtml(cell.test_number || "")}" />
          </label>
        </div>
        <div class="form-actions">
          <button class="primary-button" type="submit">Save</button>
          <button class="secondary-button" type="button" data-modal-close>Cancel</button>
        </div>
      </form>
    </div>
  `;

  document.body.appendChild(overlay);

  overlay.querySelectorAll("[data-modal-close]").forEach((btn) => {
    btn.addEventListener("click", () => overlay.remove());
  });
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });

  overlay.querySelector("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {};
    payload.cell_name = fd.get("cell_name")?.trim() || cell.cell_name;
    payload.loading = fd.get("loading") ? Number(fd.get("loading")) : null;
    payload.active_material_pct = fd.get("active_material_pct") ? Number(fd.get("active_material_pct")) : null;
    payload.electrolyte = fd.get("electrolyte")?.trim() || null;
    payload.separator = fd.get("separator")?.trim() || null;
    payload.formation_cycles = fd.get("formation_cycles") ? Number(fd.get("formation_cycles")) : 4;
    payload.group_assignment = fd.get("group_assignment")?.trim() || null;
    payload.test_number = fd.get("test_number")?.trim() || null;
    try {
      await api.updateCell(cell.id, payload);
      showToast("Cell updated.", "success");
      overlay.remove();
      await selectExperiment(state.selectedExperimentId);
    } catch (err) {
      showToast(`Update failed: ${err.message}`, "error");
    }
  });
}

function openCellDetail(cellIndex) {
  const cell = state.currentCells[cellIndex];
  if (!cell || !elements.cellDetailPanel) return;

  elements.cellDetailPanel.hidden = false;
  elements.cellDetailTitle.textContent = cell.cell_name || `Cell ${cellIndex + 1}`;

  // Metadata cards
  const meta = [
    ["Loading", cell.loading != null ? `${formatNumber(cell.loading, 2)} mg/cm²` : "—"],
    ["AM %", (cell.active_material_pct ?? cell.active_material) != null ? `${formatNumber(cell.active_material_pct ?? cell.active_material, 1)}%` : "—"],
    ["Electrolyte", cell.electrolyte || "—"],
    ["Separator", cell.separator || "—"],
    ["Formation cycles", cell.formation_cycles ?? "—"],
  ];

  const formulation = cell.formulation || [];
  if (formulation.length) {
    const formStr = formulation.map((c) =>
      `${c.Component || c.component}: ${c["Dry Mass Fraction (%)"] ?? c.dry_mass_fraction_pct ?? "?"}%`
    ).join(", ");
    meta.push(["Formulation", formStr]);
  }

  elements.cellDetailMeta.innerHTML = `
    <div class="cell-meta-grid">
      ${meta.map(([label, value]) => `
        <div class="cell-meta-item">
          <span class="cell-meta-label">${escapeHtml(label)}</span>
          <span class="cell-meta-value">${escapeHtml(String(value))}</span>
        </div>
      `).join("")}
    </div>
  `;

  // Parse cycling data
  elements.cellDetailChartsContainer.innerHTML = "";
  elements.cellDetailDataTable.innerHTML = "";
  // Remove previous health card if present
  elements.cellDetailPanel.querySelector(".cell-health-card")?.remove();

  if (!cell.data_json) {
    elements.cellDetailChartsContainer.innerHTML = renderEmptyBlock("No cycling data", "This cell has no cycling data attached.");
    return;
  }

  let data;
  try {
    data = typeof cell.data_json === "string" ? JSON.parse(cell.data_json) : cell.data_json;
  } catch (_) {
    elements.cellDetailChartsContainer.innerHTML = renderEmptyBlock("Parse error", "Could not parse cycling data.");
    return;
  }

  const cycleKeys = Object.keys(data.Cycle || {});
  if (!cycleKeys.length) {
    elements.cellDetailChartsContainer.innerHTML = renderEmptyBlock("No cycles", "Cycling data is empty.");
    return;
  }

  const cycles = cycleKeys.map((k) => data.Cycle[k]);
  const dischargeCap = cycleKeys.map((k) => data["Q Dis (mAh/g)"]?.[k]);
  const chargeCap = cycleKeys.map((k) => data["Q Chg (mAh/g)"]?.[k]);
  const efficiency = cycleKeys.map((k) => data["Efficiency (-)"]?.[k]);
  const formationCycles = cell.formation_cycles || 0;
  const startIdx = formationCycles > 0 ? formationCycles : 0;
  const baseline = dischargeCap[startIdx] || dischargeCap[0];

  // --- Compute degradation metrics ---
  const postCycles = cycles.slice(startIdx);
  const postCap = dischargeCap.slice(startIdx);
  const postEff = efficiency.slice(startIdx);

  // Linear regression for fade rate
  let fadeSlope = null, fadeIntercept = null;
  const validPairs = postCycles.map((c, i) => [c, postCap[i]]).filter(([, y]) => y != null);
  if (validPairs.length >= 3) {
    const n = validPairs.length;
    const sx = validPairs.reduce((s, [x]) => s + x, 0);
    const sy = validPairs.reduce((s, [, y]) => s + y, 0);
    const sxy = validPairs.reduce((s, [x, y]) => s + x * y, 0);
    const sx2 = validPairs.reduce((s, [x]) => s + x * x, 0);
    fadeSlope = (n * sxy - sx * sy) / (n * sx2 - sx * sx);
    fadeIntercept = (sy - fadeSlope * sx) / n;
  }

  // Predicted cycle life to 80% retention
  let predCycleTo80 = null;
  if (fadeSlope != null && fadeSlope < 0 && baseline > 0) {
    const target80 = baseline * 0.8;
    predCycleTo80 = Math.round((target80 - fadeIntercept) / fadeSlope);
    if (predCycleTo80 <= 0 || predCycleTo80 < cycles[startIdx]) predCycleTo80 = null;
  }

  // Average CE post-formation
  const validCE = postEff.filter((e) => e != null);
  const avgCE = validCE.length ? (validCE.reduce((s, e) => s + e, 0) / validCE.length) * 100 : null;

  // Last valid discharge capacity (skip trailing nulls/zeros)
  let lastValidCap = null;
  for (let i = dischargeCap.length - 1; i >= 0; i--) {
    if (dischargeCap[i] != null && dischargeCap[i] > 0) { lastValidCap = dischargeCap[i]; break; }
  }

  // Retention at final valid cycle
  const finalRetPct = baseline > 0 && lastValidCap != null ? (lastValidCap / baseline) * 100 : null;

  // Capacity differential (ΔQ per cycle)
  const deltaQ = [];
  const deltaQCycles = [];
  for (let i = 1; i < dischargeCap.length; i++) {
    if (dischargeCap[i] != null && dischargeCap[i - 1] != null) {
      deltaQ.push(dischargeCap[i] - dischargeCap[i - 1]);
      deltaQCycles.push(cycles[i]);
    }
  }

  // Health badge
  let healthLabel = "—", healthCls = "";
  if (finalRetPct != null) {
    if (finalRetPct >= 90) { healthLabel = "Good"; healthCls = "health-badge--good"; }
    else if (finalRetPct >= 80) { healthLabel = "Monitor"; healthCls = "health-badge--warn"; }
    else { healthLabel = "Poor"; healthCls = "health-badge--poor"; }
  }

  // --- Cell health summary card ---
  const healthHTML = `
    <div class="cell-health-card">
      <div class="cell-health-header">
        <span class="cell-health-title">Degradation analysis</span>
        <span class="health-badge ${healthCls}">${healthLabel}</span>
      </div>
      <div class="cell-health-metrics">
        <div class="cell-health-metric">
          <span class="cell-health-metric-label">Initial capacity</span>
          <span class="cell-health-metric-value">${dischargeCap[startIdx] != null ? formatNumber(dischargeCap[startIdx], 1) : "—"} <small>mAh/g</small></span>
        </div>
        <div class="cell-health-metric">
          <span class="cell-health-metric-label">Current capacity</span>
          <span class="cell-health-metric-value">${lastValidCap != null ? formatNumber(lastValidCap, 1) : "—"} <small>mAh/g</small></span>
        </div>
        <div class="cell-health-metric">
          <span class="cell-health-metric-label">Retention</span>
          <span class="cell-health-metric-value">${finalRetPct != null ? formatNumber(finalRetPct, 1) : "—"}<small>%</small></span>
        </div>
        <div class="cell-health-metric">
          <span class="cell-health-metric-label">Avg CE</span>
          <span class="cell-health-metric-value">${avgCE != null ? formatNumber(avgCE, 2) : "—"}<small>%</small></span>
        </div>
        <div class="cell-health-metric">
          <span class="cell-health-metric-label">Fade rate</span>
          <span class="cell-health-metric-value">${fadeSlope != null ? formatNumber(fadeSlope, 3) : "—"} <small>mAh/g/cyc</small></span>
        </div>
        <div class="cell-health-metric">
          <span class="cell-health-metric-label">Est. cycle life (80%)</span>
          <span class="cell-health-metric-value">${predCycleTo80 != null ? predCycleTo80 : "—"} <small>cycles</small></span>
        </div>
      </div>
    </div>
  `;
  elements.cellDetailChartsContainer.insertAdjacentHTML("beforebegin", healthHTML);

  if (window.Plotly) {
    const plotlyLayout = {
      margin: { t: 10, r: 40, b: 100, l: 60 },
      legend: { orientation: "h", y: -0.35, font: { size: 11 } },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: "Avenir Next, Gill Sans, sans-serif" },
      xaxis: { gridcolor: "rgba(31,26,21,0.08)", automargin: true },
      yaxis: { gridcolor: "rgba(31,26,21,0.08)" },
    };
    const plotlyConfig = { responsive: true, displayModeBar: "hover", modeBarButtonsToRemove: ["lasso2d", "select2d"] };

    // --- 1. Capacity chart with trendline ---
    const capDiv = createChartPanel("Specific Capacity", ["Capacity", "CE", "Trend"]);
    elements.cellDetailChartsContainer.append(capDiv);
    const capPlot = capDiv.querySelector(".chart-target");

    const cellCapTraces = [
      { x: cycles, y: dischargeCap, name: "Discharge", mode: "lines+markers", type: "scatter",
        line: { color: "#9a3f2b", width: 2 }, marker: { size: 5 } },
      { x: cycles, y: chargeCap, name: "Charge", mode: "lines+markers", type: "scatter",
        line: { color: "#1e6a6a", width: 2 }, marker: { size: 5 } },
    ];
    const cellCeTrace = [
      { x: cycles, y: efficiency.map((e) => e != null ? e * 100 : null), name: "CE", mode: "lines", type: "scatter",
        yaxis: "y2", visible: false, line: { color: "#3c4b63", width: 1.5, dash: "dot" }, showlegend: false },
    ];

    // Trendline + extrapolation trace
    const trendTrace = [];
    if (fadeSlope != null) {
      const lastCycle = cycles[cycles.length - 1];
      const extendTo = predCycleTo80 != null ? Math.min(predCycleTo80, lastCycle * 2) : Math.round(lastCycle * 1.5);
      const trendX = [];
      const trendY = [];
      for (let c = postCycles[0]; c <= extendTo; c += Math.max(1, Math.round((extendTo - postCycles[0]) / 100))) {
        trendX.push(c);
        trendY.push(fadeSlope * c + fadeIntercept);
      }
      trendTrace.push({
        x: trendX, y: trendY, name: "Trend (linear)", mode: "lines", type: "scatter",
        visible: false, line: { color: "#9a3f2b", width: 2, dash: "dash" }, showlegend: false,
      });
    }

    Plotly.newPlot(capPlot, [...cellCapTraces, ...cellCeTrace, ...trendTrace], {
      ...plotlyLayout,
      margin: { ...plotlyLayout.margin, r: 60 },
      xaxis: { ...plotlyLayout.xaxis, title: "Cycle" },
      yaxis: { ...plotlyLayout.yaxis, title: "Specific Capacity (mAh/g)" },
      yaxis2: { title: "CE (%)", overlaying: "y", side: "right", range: [85, 101], showgrid: false, visible: false, titlefont: { color: "#6a5d4c" }, tickfont: { color: "#6a5d4c" } },
    }, plotlyConfig);

    // Wire CE toggle
    let ceOn = false;
    let trendOn = false;
    const traceCount = cellCapTraces.length + cellCeTrace.length + trendTrace.length;
    const ceIdx = 2; // index of CE trace
    const trendIdx = trendTrace.length ? 3 : -1;

    const cellCeToggle = capDiv.querySelector('[data-chart-mode="CE"]');
    if (cellCeToggle) {
      cellCeToggle.addEventListener("click", () => {
        ceOn = !ceOn;
        cellCeToggle.classList.toggle("is-active", ceOn);
        Plotly.restyle(capPlot, { visible: ceOn }, [ceIdx]);
        Plotly.relayout(capPlot, { "yaxis2.visible": ceOn });
      });
    }

    // Wire Trend toggle
    const trendToggle = capDiv.querySelector('[data-chart-mode="Trend"]');
    if (trendToggle && trendIdx >= 0) {
      trendToggle.addEventListener("click", () => {
        trendOn = !trendOn;
        trendToggle.classList.toggle("is-active", trendOn);
        Plotly.restyle(capPlot, { visible: trendOn }, [trendIdx]);
      });
    }

    // --- 2. Retention chart with 80% threshold + prediction ---
    const retention = dischargeCap.map((cap) => baseline > 0 ? (cap / baseline) * 100 : 0);

    const retDiv = createChartPanel("Capacity Retention");
    elements.cellDetailChartsContainer.append(retDiv);
    const retPlot = retDiv.querySelector(".chart-target");

    const retTraces = [
      { x: cycles, y: retention, name: "Retention", mode: "lines+markers", type: "scatter",
        line: { color: "#9a7b2f", width: 2 }, marker: { size: 5 } },
    ];

    const retShapes = [
      { type: "line", x0: cycles[0], x1: predCycleTo80 || cycles[cycles.length - 1], y0: 80, y1: 80,
        line: { color: "rgba(154,63,43,0.4)", width: 1.5, dash: "dash" } },
    ];

    const retAnnotations = [];
    if (predCycleTo80 != null) {
      // Trendline on retention chart
      const retTrendX = [];
      const retTrendY = [];
      const c0 = postCycles[0];
      const cEnd = Math.min(predCycleTo80, cycles[cycles.length - 1] * 2);
      for (let c = c0; c <= cEnd; c += Math.max(1, Math.round((cEnd - c0) / 100))) {
        retTrendX.push(c);
        retTrendY.push(baseline > 0 ? ((fadeSlope * c + fadeIntercept) / baseline) * 100 : 0);
      }
      retTraces.push({
        x: retTrendX, y: retTrendY, name: "Projected", mode: "lines", type: "scatter",
        line: { color: "#9a7b2f", width: 2, dash: "dash" }, showlegend: true,
      });

      retAnnotations.push({
        x: predCycleTo80, y: 80,
        text: `80% @ cycle ${predCycleTo80}`,
        showarrow: true, arrowhead: 2, arrowcolor: "#9a3f2b",
        font: { size: 11, color: "#9a3f2b" },
        ax: -60, ay: -30,
      });
    }

    Plotly.newPlot(retPlot, retTraces, {
      ...plotlyLayout,
      xaxis: { ...plotlyLayout.xaxis, title: "Cycle" },
      yaxis: { ...plotlyLayout.yaxis, title: "Retention (%)", range: [Math.min(50, ...retention.filter(Boolean)) - 5, 105] },
      shapes: retShapes,
      annotations: retAnnotations,
    }, plotlyConfig);

    // --- 3. Capacity differential (ΔQ/cycle) chart ---
    if (deltaQ.length >= 2) {
      const dqDiv = createChartPanel("Capacity Differential (ΔQ/cycle)");
      elements.cellDetailChartsContainer.append(dqDiv);
      const dqPlot = dqDiv.querySelector(".chart-target");

      // Color code: negative = fading (red), positive = recovery (green)
      const dqColors = deltaQ.map((dq) => dq < -1 ? "#9a3f2b" : dq > 0.5 ? "#2d7a61" : "#8a7e6d");

      Plotly.newPlot(dqPlot, [{
        x: deltaQCycles, y: deltaQ, type: "bar",
        marker: { color: dqColors },
        hovertemplate: "Cycle %{x}<br>ΔQ: %{y:.3f} mAh/g<extra></extra>",
      }], {
        ...plotlyLayout,
        xaxis: { ...plotlyLayout.xaxis, title: "Cycle" },
        yaxis: { ...plotlyLayout.yaxis, title: "ΔQ (mAh/g)" },
        shapes: [{ type: "line", x0: deltaQCycles[0], x1: deltaQCycles[deltaQCycles.length - 1], y0: 0, y1: 0,
          line: { color: "rgba(31,26,21,0.2)", width: 1 } }],
      }, plotlyConfig);

      requestAnimationFrame(() => Plotly.Plots.resize(dqPlot));
    }

    // Deferred resize — Plotly can mis-measure width when the grid layout hasn't settled yet
    requestAnimationFrame(() => {
      Plotly.Plots.resize(capPlot);
      Plotly.Plots.resize(retPlot);
    });
  }

  // Cycle data table
  const tableRows = cycles.map((cycle, i) => {
    const ret = baseline > 0 ? ((dischargeCap[i] / baseline) * 100).toFixed(1) : "—";
    const dq = i > 0 && dischargeCap[i] != null && dischargeCap[i - 1] != null
      ? formatNumber(dischargeCap[i] - dischargeCap[i - 1], 3) : "—";
    return `
      <tr>
        <td>${cycle}</td>
        <td>${dischargeCap[i] != null ? formatNumber(dischargeCap[i], 2) : "—"}</td>
        <td>${chargeCap[i] != null ? formatNumber(chargeCap[i], 2) : "—"}</td>
        <td>${efficiency[i] != null ? formatNumber(efficiency[i] * 100, 2) : "—"}%</td>
        <td>${ret}%</td>
        <td>${dq}</td>
      </tr>
    `;
  }).join("");

  elements.cellDetailDataTable.innerHTML = `
    <details class="create-form-details" open>
      <summary class="create-form-toggle">Cycle data (${cycles.length} cycles)</summary>
      <div class="data-table-wrap" style="max-height:400px; overflow-y:auto;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Cycle</th>
              <th>Q Dis (mAh/g)</th>
              <th>Q Chg (mAh/g)</th>
              <th>CE (%)</th>
              <th>Retention (%)</th>
              <th>ΔQ</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>
    </details>
  `;

  // Scroll into view
  elements.cellDetailPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

// =====================================================================
// Experiment Charts (Plotly)
// =====================================================================

const CHART_COLORS = [
  "#9a3f2b", "#1e6a6a", "#9a7b2f", "#3c4b63", "#6f2716",
  "#2d7a61", "#7d5f16", "#1f324c", "#735b1c", "#124e4e",
];

function renderExperimentCharts(cells) {
  if (!window.Plotly || !elements.experimentChartsContainer) return;
  elements.experimentChartsContainer.innerHTML = "";

  // Parse cycling data from each cell
  const cellTraces = [];
  for (const cell of cells) {
    if (!cell.data_json) continue;
    try {
      const data = typeof cell.data_json === "string" ? JSON.parse(cell.data_json) : cell.data_json;
      const cycleKeys = Object.keys(data.Cycle || {});
      if (!cycleKeys.length) continue;

      const cycles = cycleKeys.map((k) => data.Cycle[k]);
      const dischargeCap = cycleKeys.map((k) => data["Q Dis (mAh/g)"]?.[k]);
      const chargeCap = cycleKeys.map((k) => data["Q Chg (mAh/g)"]?.[k]);
      const efficiency = cycleKeys.map((k) => data["Efficiency (-)"]?.[k]);
      const formationCycles = cell.formation_cycles || 0;

      cellTraces.push({
        name: cell.cell_name,
        cycles,
        dischargeCap,
        chargeCap,
        efficiency,
        formationCycles,
      });
    } catch (_) { /* skip cells with bad data */ }
  }

  if (!cellTraces.length) return;

  const plotlyLayout = {
    margin: { t: 10, r: 40, b: 100, l: 60 },
    legend: { orientation: "h", y: -0.35, font: { size: 11 } },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { family: "Avenir Next, Gill Sans, sans-serif" },
    xaxis: { gridcolor: "rgba(31,26,21,0.08)", automargin: true, tickmode: "auto", nticks: 10 },
    yaxis: { gridcolor: "rgba(31,26,21,0.08)", automargin: true },
  };
  const plotlyConfig = { responsive: true, displayModeBar: "hover", modeBarButtonsToRemove: ["lasso2d", "select2d"] };

  // --- 1. Specific Discharge Capacity + CE toggle ---
  const capDiv = createChartPanel("Specific Discharge Capacity", ["Capacity", "CE"]);
  elements.experimentChartsContainer.append(capDiv);
  const capPlot = capDiv.querySelector(".chart-target");

  const capTraces = cellTraces.map((cell, i) => ({
    x: cell.cycles,
    y: cell.dischargeCap,
    name: cell.name,
    mode: "lines+markers",
    type: "scatter",
    line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 },
    marker: { size: 5 },
  }));

  // CE traces on secondary y-axis, initially hidden
  const ceTraces = cellTraces.map((cell, i) => ({
    x: cell.cycles,
    y: cell.efficiency.map((e) => (e != null ? e * 100 : null)),
    name: `${cell.name} CE`,
    mode: "lines",
    type: "scatter",
    yaxis: "y2",
    visible: false,
    line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 1.5, dash: "dot" },
    marker: { size: 3 },
    showlegend: false,
  }));

  const capLayout = {
    ...plotlyLayout,
    margin: { ...plotlyLayout.margin, r: 60 },
    xaxis: { ...plotlyLayout.xaxis, title: "Cycle" },
    yaxis: { ...plotlyLayout.yaxis, title: "Specific Capacity (mAh/g)" },
    yaxis2: { title: "CE (%)", overlaying: "y", side: "right", range: [85, 101], showgrid: false, visible: false, titlefont: { color: "#6a5d4c" }, tickfont: { color: "#6a5d4c" } },
  };

  Plotly.newPlot(capPlot, [...capTraces, ...ceTraces], capLayout, plotlyConfig);

  // Wire CE toggle
  const ceToggle = capDiv.querySelector('[data-chart-mode="CE"]');
  if (ceToggle) {
    let ceVisible = false;
    ceToggle.addEventListener("click", () => {
      ceVisible = !ceVisible;
      ceToggle.classList.toggle("is-active", ceVisible);
      const visible = [];
      for (let i = 0; i < capTraces.length; i++) visible.push(true);
      for (let i = 0; i < ceTraces.length; i++) visible.push(ceVisible);
      Plotly.restyle(capPlot, { visible }, Array.from({ length: capTraces.length + ceTraces.length }, (_, i) => i));
      Plotly.relayout(capPlot, { "yaxis2.visible": ceVisible });
    });
  }

  // --- 2. Capacity Retention ---
  const retDiv = createChartPanel("Capacity Retention");
  elements.experimentChartsContainer.append(retDiv);
  const retPlot = retDiv.querySelector(".chart-target");

  const retTraces = cellTraces.map((cell, i) => {
    const startIdx = cell.formationCycles > 0 ? cell.formationCycles : 0;
    const baseline = cell.dischargeCap[startIdx] || cell.dischargeCap[0];
    const retention = cell.dischargeCap.map((cap) =>
      baseline > 0 ? (cap / baseline) * 100 : 0,
    );
    return {
      x: cell.cycles,
      y: retention,
      name: cell.name,
      mode: "lines+markers",
      type: "scatter",
      line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 },
      marker: { size: 5 },
    };
  });

  Plotly.newPlot(retPlot, retTraces, {
    ...plotlyLayout,
    xaxis: { ...plotlyLayout.xaxis, title: "Cycle" },
    yaxis: { ...plotlyLayout.yaxis, title: "Retention (%)", range: [50, 105] },
    shapes: [{ type: "line", x0: 0, x1: Math.max(...cellTraces.flatMap((c) => c.cycles)),
      y0: 80, y1: 80, line: { color: "rgba(154,63,43,0.35)", width: 1.5, dash: "dash" } }],
    annotations: [{ x: 1, xref: "paper", y: 80, yref: "y", text: "80% threshold", showarrow: false,
      font: { size: 10, color: "#9a3f2b" }, xanchor: "right", yanchor: "bottom" }],
  }, plotlyConfig);

  // Deferred resize — Plotly can mis-measure width when the grid layout hasn't settled yet
  requestAnimationFrame(() => {
    Plotly.Plots.resize(capPlot);
    Plotly.Plots.resize(retPlot);
  });
}

// =====================================================================
// Experiment Statistics & Distribution Analysis
// =====================================================================

function renderExperimentStats(cells) {
  if (!elements.experimentStatsPanel) return;

  // Parse cycling data from each cell
  const cellStats = [];
  for (const cell of cells) {
    if (!cell.data_json) continue;
    try {
      const data = typeof cell.data_json === "string" ? JSON.parse(cell.data_json) : cell.data_json;
      const cycleKeys = Object.keys(data.Cycle || {});
      if (!cycleKeys.length) continue;

      const cycles = cycleKeys.map((k) => data.Cycle[k]);
      const dischargeCap = cycleKeys.map((k) => data["Q Dis (mAh/g)"]?.[k]);
      const chargeCap = cycleKeys.map((k) => data["Q Chg (mAh/g)"]?.[k]);
      const efficiency = cycleKeys.map((k) => data["Efficiency (-)"]?.[k]);
      const formationCycles = cell.formation_cycles || 0;
      const startIdx = formationCycles > 0 ? formationCycles : 0;
      const baseline = dischargeCap[startIdx] || dischargeCap[0];

      // Initial capacity (first post-formation cycle)
      const initialCap = dischargeCap[startIdx];
      // Final capacity (last non-null/non-zero value)
      let finalCap = null;
      for (let j = dischargeCap.length - 1; j >= 0; j--) {
        if (dischargeCap[j] != null && dischargeCap[j] > 0) { finalCap = dischargeCap[j]; break; }
      }
      // Retention at final cycle
      const finalRetention = baseline > 0 && finalCap != null ? (finalCap / baseline) * 100 : null;
      // Average CE (post-formation)
      const postFormationCE = efficiency.slice(startIdx).filter((e) => e != null);
      const avgCE = postFormationCE.length > 0
        ? (postFormationCE.reduce((s, e) => s + e, 0) / postFormationCE.length) * 100
        : null;
      // Fade rate: linear slope of capacity per cycle (mAh/g per cycle)
      const postFormationCap = dischargeCap.slice(startIdx).filter((c) => c != null);
      const postFormationCycles = cycles.slice(startIdx).slice(0, postFormationCap.length);
      let fadeRate = null;
      if (postFormationCap.length >= 3) {
        const n = postFormationCap.length;
        const sumX = postFormationCycles.reduce((s, x) => s + x, 0);
        const sumY = postFormationCap.reduce((s, y) => s + y, 0);
        const sumXY = postFormationCycles.reduce((s, x, i) => s + x * postFormationCap[i], 0);
        const sumX2 = postFormationCycles.reduce((s, x) => s + x * x, 0);
        const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
        fadeRate = slope; // negative = capacity fading
      }
      // Estimated cycle life to 80% retention
      let cycleLifeTo80 = null;
      if (fadeRate != null && fadeRate < 0 && baseline > 0) {
        const target = baseline * 0.8;
        cycleLifeTo80 = Math.round((target - baseline) / fadeRate + (cycles[startIdx] || 1));
        if (cycleLifeTo80 < 0) cycleLifeTo80 = null; // not meaningful
      }

      cellStats.push({
        name: cell.cell_name,
        initialCap,
        finalCap,
        finalRetention,
        avgCE,
        fadeRate,
        cycleLifeTo80,
        totalCycles: cycles.length,
        baseline,
      });
    } catch (_) { /* skip */ }
  }

  if (cellStats.length < 2) {
    elements.experimentStatsPanel.hidden = true;
    return;
  }

  elements.experimentStatsPanel.hidden = false;
  elements.experimentStatsMeta.textContent = `${cellStats.length} cells with cycling data`;

  // --- Summary statistics ---
  const metrics = [
    { label: "Initial capacity", unit: "mAh/g", values: cellStats.map((c) => c.initialCap).filter((v) => v != null), decimals: 1 },
    { label: "Final capacity", unit: "mAh/g", values: cellStats.map((c) => c.finalCap).filter((v) => v != null), decimals: 1 },
    { label: "Retention", unit: "%", values: cellStats.map((c) => c.finalRetention).filter((v) => v != null), decimals: 1 },
    { label: "Avg CE", unit: "%", values: cellStats.map((c) => c.avgCE).filter((v) => v != null), decimals: 2 },
    { label: "Fade rate", unit: "mAh/g/cyc", values: cellStats.map((c) => c.fadeRate).filter((v) => v != null), decimals: 3 },
    { label: "Est. cycle life (80%)", unit: "cycles", values: cellStats.map((c) => c.cycleLifeTo80).filter((v) => v != null), decimals: 0 },
  ];

  const statsHTML = metrics.map((m) => {
    if (!m.values.length) return "";
    const sorted = [...m.values].sort((a, b) => a - b);
    const mean = sorted.reduce((s, v) => s + v, 0) / sorted.length;
    const variance = sorted.reduce((s, v) => s + (v - mean) ** 2, 0) / sorted.length;
    const std = Math.sqrt(variance);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const median = sorted.length % 2 === 0
      ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
      : sorted[Math.floor(sorted.length / 2)];
    const cv = mean !== 0 ? ((std / Math.abs(mean)) * 100).toFixed(1) : "—";

    return `
      <div class="stats-card">
        <div class="stats-card-label">${escapeHtml(m.label)}</div>
        <div class="stats-card-value">${formatNumber(mean, m.decimals)} <small>${escapeHtml(m.unit)}</small></div>
        <div class="stats-card-details">
          <span>σ ${formatNumber(std, m.decimals)}</span>
          <span>CV ${cv}%</span>
          <span>Med ${formatNumber(median, m.decimals)}</span>
          <span>Min ${formatNumber(min, m.decimals)}</span>
          <span>Max ${formatNumber(max, m.decimals)}</span>
        </div>
      </div>
    `;
  }).filter(Boolean).join("");

  elements.experimentStatsSummary.innerHTML = statsHTML;

  // --- Box plots (collapsed by default) ---
  elements.experimentStatsCharts.innerHTML = "";

  if (window.Plotly) {
    const plotlyConfig = { responsive: true, displayModeBar: "hover", modeBarButtonsToRemove: ["lasso2d", "select2d"] };

    // Helper: compute summary stats for an array of numbers
    function boxStats(arr) {
      const sorted = [...arr].sort((a, b) => a - b);
      const n = sorted.length;
      const mean = sorted.reduce((s, v) => s + v, 0) / n;
      const median = n % 2 === 1 ? sorted[Math.floor(n / 2)] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
      const min = sorted[0];
      const max = sorted[n - 1];
      const variance = sorted.reduce((s, v) => s + (v - mean) ** 2, 0) / (n - 1);
      const stdDev = Math.sqrt(variance);
      const cv = mean !== 0 ? (stdDev / Math.abs(mean)) * 100 : 0;
      return { n, mean, median, min, max, stdDev, cv };
    }

    // Helper: render a horizontal box plot with stats annotation
    function renderDistributionPlot(container, values, names, label, unit, color) {
      const stats = boxStats(values);
      const statsText = `n=${stats.n}  |  mean=${stats.mean.toFixed(1)}${unit}  |  median=${stats.median.toFixed(1)}${unit}  |  std=${stats.stdDev.toFixed(2)}${unit}  |  CV=${stats.cv.toFixed(1)}%`;
      const layout = {
        margin: { t: 30, r: 20, b: 40, l: 20 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { family: "Avenir Next, Gill Sans, sans-serif", size: 11 },
        xaxis: { title: label, gridcolor: "rgba(31,26,21,0.08)", automargin: true },
        yaxis: { visible: false },
        showlegend: false,
        annotations: [{
          text: statsText,
          xref: "paper", yref: "paper",
          x: 0.5, y: 1.02,
          xanchor: "center", yanchor: "bottom",
          showarrow: false,
          font: { size: 10.5, color: "#8a7e6d", family: "Avenir Next, Gill Sans, sans-serif" },
        }],
      };

      Plotly.newPlot(container, [{
        x: values,
        text: names,
        name: "",
        type: "box",
        orientation: "h",
        boxpoints: "all",
        jitter: 0.4,
        pointpos: -1.5,
        marker: { color, size: 7, opacity: 0.8 },
        line: { color },
        fillcolor: color.replace(")", ",0.15)").replace("rgb", "rgba"),
        hovertemplate: "%{text}<br>" + label + ": %{x:.1f}" + unit + "<extra></extra>",
      }], layout, plotlyConfig);
    }

    // Collect distribution data
    const distributions = [];

    const initialCaps = cellStats.map((c) => c.initialCap).filter((v) => v != null);
    if (initialCaps.length >= 2) {
      distributions.push({
        values: initialCaps,
        names: cellStats.filter((c) => c.initialCap != null).map((c) => c.name),
        label: "Specific Capacity (mAh/g)", unit: "", color: "rgb(154,63,43)", title: "Initial Capacity",
      });
    }

    const retentions = cellStats.map((c) => c.finalRetention).filter((v) => v != null);
    if (retentions.length >= 2) {
      distributions.push({
        values: retentions,
        names: cellStats.filter((c) => c.finalRetention != null).map((c) => c.name),
        label: "Retention (%)", unit: "%", color: "rgb(30,106,106)", title: "Retention",
      });
    }

    const ceValues = cellStats.map((c) => c.avgCE).filter((v) => v != null);
    if (ceValues.length >= 2) {
      distributions.push({
        values: ceValues,
        names: cellStats.filter((c) => c.avgCE != null).map((c) => c.name),
        label: "Avg Coulombic Efficiency (%)", unit: "%", color: "rgb(60,75,99)", title: "Coulombic Efficiency",
      });
    }

    if (distributions.length > 0) {
      // Wrap in a collapsed <details> since these are supplementary
      const detailsEl = document.createElement("details");
      detailsEl.className = "create-form-details";
      detailsEl.innerHTML = `<summary class="create-form-toggle">Distribution plots (${distributions.length})</summary>`;
      const chartsGrid = document.createElement("div");
      chartsGrid.className = "charts-container";
      detailsEl.append(chartsGrid);
      elements.experimentStatsCharts.append(detailsEl);

      // Render on first expand so Plotly sizes correctly
      let rendered = false;
      detailsEl.addEventListener("toggle", () => {
        if (detailsEl.open && !rendered) {
          rendered = true;
          for (const d of distributions) {
            const panel = createChartPanel(d.title + " Distribution");
            chartsGrid.append(panel);
            const target = panel.querySelector(".chart-target");
            renderDistributionPlot(target, d.values, d.names, d.label, d.unit, d.color);
          }
        }
      });
    }
  }

  // --- Fade rate ranking table ---
  const fadeRankCells = cellStats
    .filter((c) => c.fadeRate != null)
    .sort((a, b) => b.fadeRate - a.fadeRate); // least negative (least fade) first

  if (fadeRankCells.length >= 2) {
    const fadeRows = fadeRankCells.map((c, i) => {
      const rateClass = c.fadeRate > -0.5 ? "fade-good" : c.fadeRate > -1.5 ? "fade-moderate" : "fade-poor";
      return `
        <tr>
          <td>${i + 1}</td>
          <td>${escapeHtml(c.name)}</td>
          <td>${formatNumber(c.initialCap, 1)}</td>
          <td>${formatNumber(c.finalCap, 1)}</td>
          <td>${formatNumber(c.finalRetention, 1)}%</td>
          <td class="${rateClass}">${formatNumber(c.fadeRate, 3)}</td>
          <td>${c.cycleLifeTo80 != null ? c.cycleLifeTo80 : "—"}</td>
          <td>${c.totalCycles}</td>
        </tr>
      `;
    }).join("");

    elements.experimentFadeRateTable.innerHTML = `
      <div class="data-table-wrap" style="max-height:400px; overflow-y:auto;">
        <table class="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Cell</th>
              <th>Initial cap</th>
              <th>Final cap</th>
              <th>Retention</th>
              <th>Fade rate (mAh/g/cyc)</th>
              <th>Est. life (80%)</th>
              <th>Cycles</th>
            </tr>
          </thead>
          <tbody>${fadeRows}</tbody>
        </table>
      </div>
    `;
  } else {
    elements.experimentFadeRateTable.innerHTML = "";
  }
}

// =====================================================================
// Experiment Report Builder
// =====================================================================

async function generateExperimentReport() {
  if (!state.experimentDetail || !state.currentCells.length) {
    showToast("Select an experiment with cells first.", "error");
    return;
  }

  const experiment = state.experimentDetail;
  const cells = state.currentCells;
  const expName = experiment.name || experiment.cell_name || `Experiment #${experiment.id}`;
  const projectName = state.projects.find((p) => p.id === state.selectedProjectId)?.name || "—";
  const discDiameter = experiment.disc_diameter_mm ||
    (experiment.data_json ? (typeof experiment.data_json === "string" ? JSON.parse(experiment.data_json) : experiment.data_json).disc_diameter_mm : null);
  const notes = experiment.notes || experiment.experiment_notes || "";
  const reportDate = new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });

  // --- Parse cell statistics ---
  const cellStats = [];
  const cellTraces = [];
  for (const cell of cells) {
    if (!cell.data_json) continue;
    try {
      const data = typeof cell.data_json === "string" ? JSON.parse(cell.data_json) : cell.data_json;
      const cycleKeys = Object.keys(data.Cycle || {});
      if (!cycleKeys.length) continue;

      const cycles = cycleKeys.map((k) => data.Cycle[k]);
      const dischargeCap = cycleKeys.map((k) => data["Q Dis (mAh/g)"]?.[k]);
      const chargeCap = cycleKeys.map((k) => data["Q Chg (mAh/g)"]?.[k]);
      const efficiency = cycleKeys.map((k) => data["Efficiency (-)"]?.[k]);
      const formationCycles = cell.formation_cycles || 0;
      const startIdx = formationCycles > 0 ? formationCycles : 0;
      const baseline = dischargeCap[startIdx] || dischargeCap[0];
      const initialCap = dischargeCap[startIdx];
      let finalCap = null;
      for (let j = dischargeCap.length - 1; j >= 0; j--) {
        if (dischargeCap[j] != null && dischargeCap[j] > 0) { finalCap = dischargeCap[j]; break; }
      }
      const finalRetention = baseline > 0 && finalCap != null ? (finalCap / baseline) * 100 : null;
      const postFormationCE = efficiency.slice(startIdx).filter((e) => e != null);
      const avgCE = postFormationCE.length > 0
        ? (postFormationCE.reduce((s, e) => s + e, 0) / postFormationCE.length) * 100
        : null;
      const postFormationCap = dischargeCap.slice(startIdx).filter((c) => c != null);
      const postFormationCycles = cycles.slice(startIdx).slice(0, postFormationCap.length);
      let fadeRate = null;
      if (postFormationCap.length >= 3) {
        const n = postFormationCap.length;
        const sumX = postFormationCycles.reduce((s, x) => s + x, 0);
        const sumY = postFormationCap.reduce((s, y) => s + y, 0);
        const sumXY = postFormationCycles.reduce((s, x, i) => s + x * postFormationCap[i], 0);
        const sumX2 = postFormationCycles.reduce((s, x) => s + x * x, 0);
        fadeRate = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
      }
      let cycleLifeTo80 = null;
      if (fadeRate != null && fadeRate < 0 && baseline > 0) {
        const target = baseline * 0.8;
        cycleLifeTo80 = Math.round((target - baseline) / fadeRate + (cycles[startIdx] || 1));
        if (cycleLifeTo80 < 0) cycleLifeTo80 = null;
      }

      cellStats.push({ name: cell.cell_name, initialCap, finalCap, finalRetention, avgCE, fadeRate, cycleLifeTo80, totalCycles: cycles.length, baseline });
      cellTraces.push({ name: cell.cell_name, cycles, dischargeCap, chargeCap, efficiency, formationCycles });
    } catch (_) {}
  }

  // --- Compute batch summary stats ---
  function batchStat(values, decimals) {
    const v = values.filter((x) => x != null);
    if (!v.length) return null;
    const sorted = [...v].sort((a, b) => a - b);
    const mean = sorted.reduce((s, x) => s + x, 0) / sorted.length;
    const variance = sorted.reduce((s, x) => s + (x - mean) ** 2, 0) / sorted.length;
    const std = Math.sqrt(variance);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const median = sorted.length % 2 === 0
      ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
      : sorted[Math.floor(sorted.length / 2)];
    const cv = mean !== 0 ? (std / Math.abs(mean)) * 100 : 0;
    return { mean, std, min, max, median, cv, n: v.length, decimals };
  }

  const statDefs = [
    { label: "Initial Capacity", unit: "mAh/g", values: cellStats.map((c) => c.initialCap), decimals: 1 },
    { label: "Final Capacity", unit: "mAh/g", values: cellStats.map((c) => c.finalCap), decimals: 1 },
    { label: "Retention", unit: "%", values: cellStats.map((c) => c.finalRetention), decimals: 1 },
    { label: "Avg CE", unit: "%", values: cellStats.map((c) => c.avgCE), decimals: 2 },
    { label: "Fade Rate", unit: "mAh/g/cyc", values: cellStats.map((c) => c.fadeRate), decimals: 3 },
    { label: "Est. Cycle Life (80%)", unit: "cycles", values: cellStats.map((c) => c.cycleLifeTo80), decimals: 0 },
  ];

  const batchStats = statDefs.map((d) => ({ ...d, stat: batchStat(d.values, d.decimals) })).filter((d) => d.stat);

  // --- Build cell table rows ---
  const cellTableRows = cells.map((cell) => {
    const am = cell.active_material_pct ?? cell.active_material;
    const stat = cellStats.find((s) => s.name === cell.cell_name);
    return `<tr>
      <td>${escapeHtml(cell.cell_name)}</td>
      <td>${cell.loading != null ? formatNumber(cell.loading, 2) : "—"}</td>
      <td>${am != null ? formatNumber(am, 1) + "%" : "—"}</td>
      <td>${escapeHtml(cell.electrolyte || "—")}</td>
      <td>${escapeHtml(cell.separator || "—")}</td>
      <td>${cell.formation_cycles ?? "—"}</td>
      <td>${stat ? formatNumber(stat.initialCap, 1) : "—"}</td>
      <td>${stat ? formatNumber(stat.finalCap, 1) : "—"}</td>
      <td>${stat && stat.finalRetention != null ? formatNumber(stat.finalRetention, 1) + "%" : "—"}</td>
      <td>${stat && stat.avgCE != null ? formatNumber(stat.avgCE, 2) + "%" : "—"}</td>
    </tr>`;
  }).join("");

  // --- Build fade rate ranking ---
  const fadeRankCells = cellStats.filter((c) => c.fadeRate != null).sort((a, b) => b.fadeRate - a.fadeRate);
  const fadeRankRows = fadeRankCells.map((c, i) => {
    const rateClass = c.fadeRate > -0.5 ? "fade-good" : c.fadeRate > -1.5 ? "fade-moderate" : "fade-poor";
    return `<tr>
      <td>${i + 1}</td>
      <td>${escapeHtml(c.name)}</td>
      <td>${formatNumber(c.initialCap, 1)}</td>
      <td>${formatNumber(c.finalCap, 1)}</td>
      <td>${formatNumber(c.finalRetention, 1)}%</td>
      <td class="${rateClass}">${formatNumber(c.fadeRate, 3)}</td>
      <td>${c.cycleLifeTo80 != null ? c.cycleLifeTo80 : "—"}</td>
      <td>${c.totalCycles}</td>
    </tr>`;
  }).join("");

  // --- Build batch statistics table ---
  const batchStatsRows = batchStats.map((d) => {
    const s = d.stat;
    return `<tr>
      <td><strong>${escapeHtml(d.label)}</strong></td>
      <td>${formatNumber(s.mean, s.decimals)} ${escapeHtml(d.unit)}</td>
      <td>${formatNumber(s.std, s.decimals)}</td>
      <td>${s.cv.toFixed(1)}%</td>
      <td>${formatNumber(s.median, s.decimals)}</td>
      <td>${formatNumber(s.min, s.decimals)}</td>
      <td>${formatNumber(s.max, s.decimals)}</td>
      <td>${s.n}</td>
    </tr>`;
  }).join("");

  // --- Build overall health assessment ---
  const avgRetention = cellStats.map((c) => c.finalRetention).filter((v) => v != null);
  const meanRetention = avgRetention.length ? avgRetention.reduce((s, v) => s + v, 0) / avgRetention.length : null;
  const avgCEvals = cellStats.map((c) => c.avgCE).filter((v) => v != null);
  const meanCE = avgCEvals.length ? avgCEvals.reduce((s, v) => s + v, 0) / avgCEvals.length : null;
  let healthSummary = "";
  if (meanRetention != null) {
    const healthLabel = meanRetention >= 90 ? "Good" : meanRetention >= 80 ? "Monitor" : "Poor";
    const healthColor = meanRetention >= 90 ? "#2d7a61" : meanRetention >= 80 ? "#9a7b2f" : "#9a3f2b";
    healthSummary = `<div class="report-health-badge" style="border-color:${healthColor};color:${healthColor}">
      Batch Health: ${healthLabel} — ${formatNumber(meanRetention, 1)}% avg retention${meanCE != null ? `, ${formatNumber(meanCE, 2)}% avg CE` : ""}
    </div>`;
  }

  // --- Assemble report HTML ---
  const reportHTML = `
    <div class="report-page">
      <header class="report-header">
        <div class="report-brand">
          <div class="report-brand-mark">CS</div>
          <div>
            <div class="report-brand-name">CellScope 2.0</div>
            <div class="report-brand-sub">Experiment Report</div>
          </div>
        </div>
        <div class="report-header-meta">
          <div class="report-date">${escapeHtml(reportDate)}</div>
        </div>
      </header>

      <section class="report-section">
        <h2 class="report-title">${escapeHtml(expName)}</h2>
        <div class="report-meta-grid">
          <div class="report-meta-item"><span class="report-meta-label">Project</span><span>${escapeHtml(projectName)}</span></div>
          <div class="report-meta-item"><span class="report-meta-label">Cells</span><span>${cells.length} total, ${cellStats.length} with cycling data</span></div>
          ${discDiameter ? `<div class="report-meta-item"><span class="report-meta-label">Disc diameter</span><span>${discDiameter} mm</span></div>` : ""}
          ${notes ? `<div class="report-meta-item report-meta-item--wide"><span class="report-meta-label">Notes</span><span>${escapeHtml(notes)}</span></div>` : ""}
        </div>
        ${healthSummary}
      </section>

      <section class="report-section">
        <h3 class="report-section-title">Cell Summary</h3>
        <table class="report-table">
          <thead><tr>
            <th>Cell</th><th>Loading</th><th>AM %</th><th>Electrolyte</th><th>Separator</th>
            <th>Form.</th><th>Init. Cap</th><th>Final Cap</th><th>Retention</th><th>Avg CE</th>
          </tr></thead>
          <tbody>${cellTableRows}</tbody>
        </table>
      </section>

      ${cellTraces.length ? `
      <section class="report-section">
        <h3 class="report-section-title">Performance Charts</h3>
        <div class="report-charts-grid">
          <div class="report-chart-slot">
            <h4 class="report-chart-label">Specific Discharge Capacity</h4>
            <div id="reportChartCapacity" class="report-chart-target"></div>
          </div>
          <div class="report-chart-slot">
            <h4 class="report-chart-label">Capacity Retention</h4>
            <div id="reportChartRetention" class="report-chart-target"></div>
          </div>
          <div class="report-chart-slot">
            <h4 class="report-chart-label">Coulombic Efficiency</h4>
            <div id="reportChartCE" class="report-chart-target"></div>
          </div>
        </div>
      </section>` : ""}

      ${batchStats.length ? `
      <section class="report-section">
        <h3 class="report-section-title">Batch Statistics</h3>
        <table class="report-table report-table--stats">
          <thead><tr>
            <th>Metric</th><th>Mean</th><th>&sigma;</th><th>CV</th><th>Median</th><th>Min</th><th>Max</th><th>n</th>
          </tr></thead>
          <tbody>${batchStatsRows}</tbody>
        </table>
      </section>` : ""}

      ${fadeRankRows ? `
      <section class="report-section">
        <h3 class="report-section-title">Cell Ranking — Fade Rate</h3>
        <table class="report-table">
          <thead><tr>
            <th>#</th><th>Cell</th><th>Init. Cap</th><th>Final Cap</th><th>Retention</th>
            <th>Fade Rate</th><th>Est. Life (80%)</th><th>Cycles</th>
          </tr></thead>
          <tbody>${fadeRankRows}</tbody>
        </table>
      </section>` : ""}

      <footer class="report-footer">
        <p>Generated by CellScope 2.0 &mdash; ${escapeHtml(reportDate)}</p>
      </footer>
    </div>
  `;

  elements.reportContent.innerHTML = reportHTML;
  elements.reportOverlay.hidden = false;
  document.body.classList.add("report-printing");

  // Scroll to top of report
  elements.reportContent.scrollTop = 0;

  // --- Render Plotly charts into the report ---
  if (window.Plotly && cellTraces.length) {
    const reportLayout = {
      margin: { t: 8, r: 30, b: 90, l: 56 },
      legend: { orientation: "h", y: -0.35, font: { size: 10 } },
      paper_bgcolor: "#ffffff",
      plot_bgcolor: "#ffffff",
      font: { family: "Avenir Next, Gill Sans, sans-serif", size: 11 },
      xaxis: { gridcolor: "rgba(31,26,21,0.1)", automargin: true, title: "Cycle" },
      yaxis: { gridcolor: "rgba(31,26,21,0.1)", automargin: true },
    };
    const reportConfig = { responsive: true, staticPlot: true, displayModeBar: false };

    // Capacity chart
    const capEl = document.getElementById("reportChartCapacity");
    if (capEl) {
      const capTraces = cellTraces.map((cell, i) => ({
        x: cell.cycles, y: cell.dischargeCap, name: cell.name,
        mode: "lines+markers", type: "scatter",
        line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 }, marker: { size: 4 },
      }));
      Plotly.newPlot(capEl, capTraces, { ...reportLayout, yaxis: { ...reportLayout.yaxis, title: "Specific Capacity (mAh/g)" } }, reportConfig);
    }

    // Retention chart
    const retEl = document.getElementById("reportChartRetention");
    if (retEl) {
      const retTraces = cellTraces.map((cell, i) => {
        const startIdx = cell.formationCycles > 0 ? cell.formationCycles : 0;
        const baseline = cell.dischargeCap[startIdx] || cell.dischargeCap[0];
        const retention = cell.dischargeCap.map((cap) => baseline > 0 ? (cap / baseline) * 100 : 0);
        return { x: cell.cycles, y: retention, name: cell.name, mode: "lines+markers", type: "scatter",
          line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 }, marker: { size: 4 } };
      });
      Plotly.newPlot(retEl, retTraces, {
        ...reportLayout,
        yaxis: { ...reportLayout.yaxis, title: "Retention (%)", range: [50, 105] },
        shapes: [{ type: "line", x0: 0, x1: Math.max(...cellTraces.flatMap((c) => c.cycles)),
          y0: 80, y1: 80, line: { color: "rgba(154,63,43,0.35)", width: 1.5, dash: "dash" } }],
      }, reportConfig);
    }

    // CE chart
    const ceEl = document.getElementById("reportChartCE");
    if (ceEl) {
      const ceTraces = cellTraces.map((cell, i) => ({
        x: cell.cycles, y: cell.efficiency.map((e) => e != null ? e * 100 : null), name: cell.name,
        mode: "lines+markers", type: "scatter",
        line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 }, marker: { size: 4 },
      }));
      Plotly.newPlot(ceEl, ceTraces, { ...reportLayout, yaxis: { ...reportLayout.yaxis, title: "Coulombic Efficiency (%)" } }, reportConfig);
    }
  }

  showToast("Report generated. Use Print to save as PDF.", "success");
}

function createChartPanel(title, toggleModes) {
  const div = document.createElement("div");
  div.className = "chart-panel";
  const toggleHTML = toggleModes
    ? `<div class="chart-toggle-group">${toggleModes.map((mode, i) =>
        `<button class="chart-toggle${i === 0 ? " is-active" : ""}" data-chart-mode="${escapeHtml(mode)}" type="button">${escapeHtml(mode)}</button>`
      ).join("")}</div>`
    : "";

  div.innerHTML = `
    <div class="chart-panel-header">
      <h4>${escapeHtml(title)}</h4>
      <div class="chart-header-actions">
        ${toggleHTML}
        <button class="chart-customize-btn" type="button" title="Customize chart">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
        </button>
      </div>
    </div>
    <div class="chart-toolbar-popover" hidden>
      <div class="ct-popover-tabs">
        <button class="ct-tab is-active" data-ct-tab="axes" type="button">Axes</button>
        <button class="ct-tab" data-ct-tab="filter" type="button">Filter</button>
        <button class="ct-tab" data-ct-tab="style" type="button">Style</button>
        <button class="ct-tab" data-ct-tab="export" type="button">Export</button>
      </div>
      <div class="ct-tab-pane is-active" data-ct-pane="axes">
        <label class="ct-field"><span>Chart title</span><input class="ct-input chart-tb-title" type="text" placeholder="Enter title…" value="${escapeHtml(title)}"></label>
        <label class="ct-field"><span>Show title</span><input type="checkbox" class="ct-check chart-tb-show-title" checked></label>
        <div class="ct-divider"></div>
        <div class="ct-row">
          <label class="ct-field ct-grow"><span>X label</span><input class="ct-input chart-tb-xlabel" type="text" placeholder="Auto"></label>
          <label class="ct-field ct-sm"><span>Min</span><input class="ct-input chart-tb-xmin" type="number" placeholder="Auto" step="any"></label>
          <label class="ct-field ct-sm"><span>Max</span><input class="ct-input chart-tb-xmax" type="number" placeholder="Auto" step="any"></label>
        </div>
        <div class="ct-row">
          <label class="ct-field ct-grow"><span>Y label</span><input class="ct-input chart-tb-ylabel" type="text" placeholder="Auto"></label>
          <label class="ct-field ct-sm"><span>Min</span><input class="ct-input chart-tb-ymin" type="number" placeholder="Auto" step="any"></label>
          <label class="ct-field ct-sm"><span>Max</span><input class="ct-input chart-tb-ymax" type="number" placeholder="Auto" step="any"></label>
        </div>
      </div>
      <div class="ct-tab-pane" data-ct-pane="filter" hidden>
        <div class="ct-row">
          <label class="ct-field ct-sm"><span>From cycle</span><input class="ct-input chart-tb-cycle-min" type="number" placeholder="Start" min="0" step="1"></label>
          <label class="ct-field ct-sm"><span>To cycle</span><input class="ct-input chart-tb-cycle-max" type="number" placeholder="End" step="1"></label>
          <div class="ct-btn-group">
            <button class="ct-btn ct-btn-primary chart-tb-cycle-apply" type="button">Apply</button>
            <button class="ct-btn ct-btn-ghost chart-tb-cycle-reset" type="button">Reset</button>
          </div>
        </div>
      </div>
      <div class="ct-tab-pane" data-ct-pane="style" hidden>
        <div class="ct-row">
          <label class="ct-field"><span>Line mode</span>
            <select class="ct-select chart-tb-line-mode">
              <option value="lines+markers">Lines + Markers</option>
              <option value="lines">Lines only</option>
              <option value="markers">Markers only</option>
            </select>
          </label>
          <label class="ct-field ct-sm"><span>Width</span><input class="ct-input chart-tb-line-width" type="number" value="2" min="0.5" max="8" step="0.5"></label>
          <label class="ct-field ct-sm"><span>Marker</span><input class="ct-input chart-tb-marker-size" type="number" value="4" min="1" max="16" step="1"></label>
        </div>
        <div class="ct-row">
          <label class="ct-field"><span>Legend</span>
            <select class="ct-select chart-tb-legend-pos">
              <option value="bottom">Bottom</option>
              <option value="top">Top</option>
              <option value="right">Right</option>
              <option value="topright">Inside (top-right)</option>
            </select>
          </label>
          <label class="ct-field"><span>Legend size</span>
            <select class="ct-select chart-tb-legend-size">
              <option value="10">Small</option>
              <option value="12" selected>Medium</option>
              <option value="14">Large</option>
            </select>
          </label>
          <label class="ct-field"><span>Show</span><input type="checkbox" class="ct-check chart-tb-legend-show" checked></label>
        </div>
        <div class="ct-divider"></div>
        <div class="ct-row">
          <label class="ct-field"><span>Background</span>
            <select class="ct-select chart-tb-bg-color">
              <option value="transparent">Transparent</option>
              <option value="#ffffff">White</option>
              <option value="#faf8f5">Warm white</option>
              <option value="#f5f5f5">Light gray</option>
            </select>
          </label>
          <label class="ct-field"><span>X grid</span><input type="checkbox" class="ct-check chart-tb-grid-x" checked></label>
          <label class="ct-field"><span>Y grid</span><input type="checkbox" class="ct-check chart-tb-grid-y" checked></label>
        </div>
      </div>
      <div class="ct-tab-pane" data-ct-pane="export" hidden>
        <p class="ct-hint">Export a high-resolution image for reports and presentations.</p>
        <div class="ct-row">
          <button class="ct-btn ct-btn-primary chart-export-btn" type="button">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Download PNG
          </button>
          <button class="ct-btn ct-btn-ghost chart-export-svg-btn" type="button">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Download SVG
          </button>
        </div>
      </div>
    </div>
    <div class="chart-target" style="width:100%;height:340px"></div>
  `;

  // Wire up toolbar events after DOM is ready
  requestAnimationFrame(() => wireChartToolbar(div));

  return div;
}

function wireChartToolbar(panel) {
  const popover = panel.querySelector(".chart-toolbar-popover");
  const plotEl = panel.querySelector(".chart-target");
  const customizeBtn = panel.querySelector(".chart-customize-btn");
  const exportPngBtn = panel.querySelector(".chart-export-btn");
  const exportSvgBtn = panel.querySelector(".chart-export-svg-btn");

  // Toggle popover visibility
  customizeBtn.addEventListener("click", () => {
    const hidden = popover.hidden;
    popover.hidden = !hidden;
    customizeBtn.classList.toggle("is-active", hidden);
  });

  // Tab switching within popover
  popover.querySelectorAll(".ct-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      popover.querySelectorAll(".ct-tab").forEach((t) => t.classList.remove("is-active"));
      popover.querySelectorAll(".ct-tab-pane").forEach((p) => { p.hidden = true; p.classList.remove("is-active"); });
      tab.classList.add("is-active");
      const pane = popover.querySelector(`[data-ct-pane="${tab.dataset.ctTab}"]`);
      if (pane) { pane.hidden = false; pane.classList.add("is-active"); }
    });
  });

  // Export PNG
  exportPngBtn.addEventListener("click", () => {
    if (!window.Plotly || !plotEl.data) return;
    const titleInput = panel.querySelector(".chart-tb-title");
    const filename = (titleInput?.value || "chart").replace(/[^a-zA-Z0-9_-]/g, "_");
    Plotly.downloadImage(plotEl, { format: "png", width: 1200, height: 700, filename, scale: 2 });
  });

  // Export SVG
  exportSvgBtn.addEventListener("click", () => {
    if (!window.Plotly || !plotEl.data) return;
    const titleInput = panel.querySelector(".chart-tb-title");
    const filename = (titleInput?.value || "chart").replace(/[^a-zA-Z0-9_-]/g, "_");
    Plotly.downloadImage(plotEl, { format: "svg", width: 1200, height: 700, filename });
  });

  // Title
  const titleInput = panel.querySelector(".chart-tb-title");
  const showTitleCb = panel.querySelector(".chart-tb-show-title");
  const applyTitle = () => {
    if (!plotEl.data) return;
    const show = showTitleCb.checked;
    Plotly.relayout(plotEl, {
      title: show ? { text: titleInput.value, font: { family: "Avenir Next, Gill Sans, sans-serif", size: 16 }, x: 0.5 } : "",
    });
  };
  titleInput.addEventListener("change", applyTitle);
  showTitleCb.addEventListener("change", applyTitle);

  // X-Axis label and range
  const xlabelInput = panel.querySelector(".chart-tb-xlabel");
  const xminInput = panel.querySelector(".chart-tb-xmin");
  const xmaxInput = panel.querySelector(".chart-tb-xmax");

  const applyXAxis = () => {
    if (!plotEl.data) return;
    const update = {};
    if (xlabelInput.value) update["xaxis.title"] = xlabelInput.value;
    const xmin = xminInput.value !== "" ? parseFloat(xminInput.value) : null;
    const xmax = xmaxInput.value !== "" ? parseFloat(xmaxInput.value) : null;
    if (xmin !== null || xmax !== null) {
      update["xaxis.range"] = [xmin ?? plotEl.layout.xaxis?.range?.[0] ?? 0, xmax ?? plotEl.layout.xaxis?.range?.[1] ?? 100];
      update["xaxis.autorange"] = false;
    } else {
      update["xaxis.autorange"] = true;
    }
    Plotly.relayout(plotEl, update);
  };
  xlabelInput.addEventListener("change", applyXAxis);
  xminInput.addEventListener("change", applyXAxis);
  xmaxInput.addEventListener("change", applyXAxis);

  // Y-Axis label and range
  const ylabelInput = panel.querySelector(".chart-tb-ylabel");
  const yminInput = panel.querySelector(".chart-tb-ymin");
  const ymaxInput = panel.querySelector(".chart-tb-ymax");

  const applyYAxis = () => {
    if (!plotEl.data) return;
    const update = {};
    if (ylabelInput.value) update["yaxis.title"] = ylabelInput.value;
    const ymin = yminInput.value !== "" ? parseFloat(yminInput.value) : null;
    const ymax = ymaxInput.value !== "" ? parseFloat(ymaxInput.value) : null;
    if (ymin !== null || ymax !== null) {
      update["yaxis.range"] = [ymin ?? plotEl.layout.yaxis?.range?.[0] ?? 0, ymax ?? plotEl.layout.yaxis?.range?.[1] ?? 100];
      update["yaxis.autorange"] = false;
    } else {
      update["yaxis.autorange"] = true;
    }
    Plotly.relayout(plotEl, update);
  };
  ylabelInput.addEventListener("change", applyYAxis);
  yminInput.addEventListener("change", applyYAxis);
  ymaxInput.addEventListener("change", applyYAxis);

  // Cycle range filter — store original data so we can reset
  const cycleMinInput = panel.querySelector(".chart-tb-cycle-min");
  const cycleMaxInput = panel.querySelector(".chart-tb-cycle-max");
  const cycleApplyBtn = panel.querySelector(".chart-tb-cycle-apply");
  const cycleResetBtn = panel.querySelector(".chart-tb-cycle-reset");

  cycleApplyBtn.addEventListener("click", () => {
    if (!plotEl.data) return;
    const cmin = cycleMinInput.value !== "" ? parseInt(cycleMinInput.value, 10) : -Infinity;
    const cmax = cycleMaxInput.value !== "" ? parseInt(cycleMaxInput.value, 10) : Infinity;

    // Store originals on first filter
    if (!plotEl._origData) {
      plotEl._origData = plotEl.data.map((trace) => ({ x: [...trace.x], y: [...trace.y] }));
    }

    const updates = { x: [], y: [] };
    plotEl._origData.forEach((orig, i) => {
      const filteredX = [];
      const filteredY = [];
      orig.x.forEach((xv, j) => {
        if (xv >= cmin && xv <= cmax) {
          filteredX.push(xv);
          filteredY.push(orig.y[j]);
        }
      });
      updates.x.push(filteredX);
      updates.y.push(filteredY);
    });

    Plotly.restyle(plotEl, { x: updates.x, y: updates.y });
  });

  cycleResetBtn.addEventListener("click", () => {
    if (!plotEl._origData || !plotEl.data) return;
    const updates = { x: [], y: [] };
    plotEl._origData.forEach((orig) => {
      updates.x.push([...orig.x]);
      updates.y.push([...orig.y]);
    });
    Plotly.restyle(plotEl, { x: updates.x, y: updates.y });
    cycleMinInput.value = "";
    cycleMaxInput.value = "";
  });

  // Legend controls
  const legendShowCb = panel.querySelector(".chart-tb-legend-show");
  const legendPosSelect = panel.querySelector(".chart-tb-legend-pos");
  const legendSizeSelect = panel.querySelector(".chart-tb-legend-size");

  const applyLegend = () => {
    if (!plotEl.data) return;
    const show = legendShowCb.checked;
    const pos = legendPosSelect.value;
    const fontSize = parseInt(legendSizeSelect.value, 10);
    const legendUpdate = { showlegend: show };

    if (pos === "bottom") {
      legendUpdate.legend = { orientation: "h", x: 0.5, xanchor: "center", y: -0.25, font: { size: fontSize } };
    } else if (pos === "top") {
      legendUpdate.legend = { orientation: "h", x: 0.5, xanchor: "center", y: 1.12, font: { size: fontSize } };
    } else if (pos === "right") {
      legendUpdate.legend = { orientation: "v", x: 1.02, y: 1, font: { size: fontSize } };
    } else if (pos === "topright") {
      legendUpdate.legend = { orientation: "v", x: 0.98, xanchor: "right", y: 0.98, yanchor: "top", bgcolor: "rgba(255,255,255,0.8)", bordercolor: "rgba(0,0,0,0.1)", borderwidth: 1, font: { size: fontSize } };
    }
    Plotly.relayout(plotEl, legendUpdate);
  };
  legendShowCb.addEventListener("change", applyLegend);
  legendPosSelect.addEventListener("change", applyLegend);
  legendSizeSelect.addEventListener("change", applyLegend);

  // Line style controls
  const lineModeSelect = panel.querySelector(".chart-tb-line-mode");
  const lineWidthInput = panel.querySelector(".chart-tb-line-width");
  const markerSizeInput = panel.querySelector(".chart-tb-marker-size");

  const applyLineStyle = () => {
    if (!plotEl.data) return;
    const mode = lineModeSelect.value;
    const width = parseFloat(lineWidthInput.value) || 2;
    const msize = parseInt(markerSizeInput.value, 10) || 4;
    const traceCount = plotEl.data.length;
    Plotly.restyle(plotEl, {
      mode: Array(traceCount).fill(mode),
      "line.width": Array(traceCount).fill(width),
      "marker.size": Array(traceCount).fill(msize),
    });
  };
  lineModeSelect.addEventListener("change", applyLineStyle);
  lineWidthInput.addEventListener("change", applyLineStyle);
  markerSizeInput.addEventListener("change", applyLineStyle);

  // Grid & background
  const gridXCb = panel.querySelector(".chart-tb-grid-x");
  const gridYCb = panel.querySelector(".chart-tb-grid-y");
  const bgColorSelect = panel.querySelector(".chart-tb-bg-color");

  const applyGrid = () => {
    if (!plotEl.data) return;
    Plotly.relayout(plotEl, {
      "xaxis.showgrid": gridXCb.checked,
      "yaxis.showgrid": gridYCb.checked,
      plot_bgcolor: bgColorSelect.value,
      paper_bgcolor: bgColorSelect.value === "transparent" ? "transparent" : bgColorSelect.value,
    });
  };
  gridXCb.addEventListener("change", applyGrid);
  gridYCb.addEventListener("change", applyGrid);
  bgColorSelect.addEventListener("change", applyGrid);

  // Pre-populate axis labels from plotly layout once chart is rendered
  const observer = new MutationObserver(() => {
    if (plotEl.layout) {
      if (plotEl.layout.xaxis?.title) {
        const xt = typeof plotEl.layout.xaxis.title === "string" ? plotEl.layout.xaxis.title : plotEl.layout.xaxis.title.text;
        if (xt && !xlabelInput.value) xlabelInput.value = xt;
      }
      if (plotEl.layout.yaxis?.title) {
        const yt = typeof plotEl.layout.yaxis.title === "string" ? plotEl.layout.yaxis.title : plotEl.layout.yaxis.title.text;
        if (yt && !ylabelInput.value) ylabelInput.value = yt;
      }
      observer.disconnect();
    }
  });
  observer.observe(plotEl, { childList: true, subtree: true });
}

// =====================================================================
// Workspaces & Cohorts
// =====================================================================

async function loadWorkspacesAndCohorts() {
  await Promise.allSettled([loadStudyWorkspaces(), loadCohortSnapshots()]);
}

async function loadStudyWorkspaces() {
  try {
    state.studyWorkspaces = await api.listStudyWorkspaces();
    renderWorkspacesList();
  } catch (error) {
    elements.workspacesList.innerHTML = renderEmptyBlock("Workspaces unavailable", error.message);
  }
}

function renderWorkspacesList() {
  if (!state.studyWorkspaces.length) {
    elements.workspacesList.innerHTML = renderEmptyBlock(
      "No study workspaces",
      "Workspaces are created from cohort snapshots in the analysis workflow.",
    );
    return;
  }

  elements.workspacesList.innerHTML = state.studyWorkspaces
    .map((ws) => {
      const isSelected = ws.id === state.selectedWorkspaceId;
      return `
        <button class="entity-list-button ${isSelected ? "is-selected" : ""}" data-workspace-id="${ws.id}">
          <span class="entity-list-title">${escapeHtml(ws.name)}</span>
          <span class="entity-list-meta">${ws.item_count} items · ${ws.annotation_count} notes · ${escapeHtml(ws.status)}</span>
        </button>
      `;
    })
    .join("");
}

async function loadCohortSnapshots() {
  try {
    state.cohortSnapshots = await api.listCohortSnapshots();
    renderCohortSnapshotsList();
  } catch (error) {
    elements.cohortSnapshotsList.innerHTML = renderEmptyBlock("Cohort snapshots unavailable", error.message);
  }
}

function renderCohortSnapshotsList() {
  if (!state.cohortSnapshots.length) {
    elements.cohortSnapshotsList.innerHTML = renderEmptyBlock(
      "No cohort snapshots",
      "Snapshots are created from saved cohort definitions.",
    );
    return;
  }

  elements.cohortSnapshotsList.innerHTML = state.cohortSnapshots
    .map((snap) => {
      const isSelected = snap.id === state.selectedCohortSnapshotId;
      return `
        <button class="entity-list-button ${isSelected ? "is-selected" : ""}" data-snapshot-id="${snap.id}">
          <span class="entity-list-title">${escapeHtml(snap.name)}</span>
          <span class="entity-list-meta">${snap.experiment_ids.length} experiments · ${escapeHtml(snap.cohort_name || "unnamed cohort")}</span>
        </button>
      `;
    })
    .join("");
}

async function selectWorkspace(workspaceId) {
  state.selectedWorkspaceId = workspaceId;
  state.selectedCohortSnapshotId = null;
  renderWorkspacesList();
  renderCohortSnapshotsList();

  elements.workspaceDetailTitle.textContent = "Loading workspace…";
  elements.workspaceDetailMeta.textContent = "";
  elements.workspaceDetailBody.innerHTML = '<div class="loading-block">Loading…</div>';
  elements.workspaceMembersContainer.innerHTML = "";
  if (elements.widgetCanvas) elements.widgetCanvas.hidden = true;
  if (elements.widgetGrid) elements.widgetGrid.innerHTML = "";
  if (elements.manageWidgetsSidebar) elements.manageWidgetsSidebar.hidden = true;
  elements.workspaceAnnotationsContainer.innerHTML = "";

  // Show workspace-specific actions
  if (elements.workspaceActions) elements.workspaceActions.hidden = false;
  if (elements.openAsWorkspaceButton) elements.openAsWorkspaceButton.hidden = true;
  if (elements.deleteWorkspaceButton) elements.deleteWorkspaceButton.hidden = false;
  if (elements.workspaceAnnotationFormContainer) elements.workspaceAnnotationFormContainer.hidden = false;

  try {
    const payload = await api.getStudyWorkspace(workspaceId);
    state.workspaceDetail = payload;

    const summary = payload.summary || {};
    elements.workspaceDetailTitle.textContent = summary.name || `Workspace #${workspaceId}`;
    elements.workspaceDetailMeta.textContent = summary.description || "";

    // Summary stats
    const stats = [];
    if (summary.experiment_count != null) stats.push({ label: "Experiments", value: summary.experiment_count });
    if (summary.cell_count != null) stats.push({ label: "Cells", value: summary.cell_count });
    if (summary.project_count != null) stats.push({ label: "Projects", value: summary.project_count });

    elements.workspaceDetailBody.innerHTML = stats.length
      ? `<div class="stat-row">${stats.map((s) => `
          <div class="stat-item">
            <span class="stat-label">${escapeHtml(s.label)}</span>
            <span class="stat-value">${escapeHtml(String(s.value))}</span>
          </div>
        `).join("")}</div>`
      : "";

    // Members table
    renderWorkspaceMembers(payload.members || []);

    // Annotations
    renderWorkspaceAnnotations(payload.annotations || []);

    // Widget canvas
    renderWorkspaceCanvas();
  } catch (error) {
    elements.workspaceDetailTitle.textContent = "Error";
    elements.workspaceDetailMeta.textContent = error.message;
    elements.workspaceDetailBody.innerHTML = renderEmptyBlock("Workspace unavailable", error.message);
  }
}

async function selectCohortSnapshot(snapshotId) {
  state.selectedCohortSnapshotId = snapshotId;
  state.selectedWorkspaceId = null;
  renderWorkspacesList();
  renderCohortSnapshotsList();

  elements.workspaceDetailTitle.textContent = "Loading cohort snapshot…";
  elements.workspaceDetailMeta.textContent = "";
  elements.workspaceDetailBody.innerHTML = '<div class="loading-block">Loading…</div>';
  elements.workspaceMembersContainer.innerHTML = "";
  if (elements.widgetCanvas) elements.widgetCanvas.hidden = true;
  if (elements.manageWidgetsSidebar) elements.manageWidgetsSidebar.hidden = true;
  elements.workspaceAnnotationsContainer.innerHTML = "";

  // Show snapshot-specific actions
  if (elements.workspaceActions) elements.workspaceActions.hidden = false;
  if (elements.openAsWorkspaceButton) elements.openAsWorkspaceButton.hidden = false;
  if (elements.deleteWorkspaceButton) elements.deleteWorkspaceButton.hidden = true;
  if (elements.workspaceAnnotationFormContainer) elements.workspaceAnnotationFormContainer.hidden = true;

  try {
    const snapshot = await api.getCohortSnapshot(snapshotId);
    state.cohortSnapshotDetail = snapshot;

    elements.workspaceDetailTitle.textContent = snapshot.name;
    elements.workspaceDetailMeta.textContent = `${snapshot.experiment_ids.length} experiments · ${snapshot.cohort_name || "unnamed cohort"}`;

    // AI summary
    const blocks = [];
    if (snapshot.ai_summary_text) {
      blocks.push(`
        <div class="ai-summary-block">
          <h4>AI Summary</h4>
          <p>${escapeHtml(snapshot.ai_summary_text)}</p>
        </div>
      `);
    }

    // Snapshot summary stats
    const summary = snapshot.summary || {};
    const statPairs = Object.entries(summary).slice(0, 8);
    if (statPairs.length) {
      blocks.push(`
        <div class="stat-row">
          ${statPairs.map(([key, value]) => `
            <div class="stat-item">
              <span class="stat-label">${escapeHtml(key)}</span>
              <span class="stat-value">${escapeHtml(String(typeof value === "number" ? formatNumber(value, 2) : value))}</span>
            </div>
          `).join("")}
        </div>
      `);
    }

    elements.workspaceDetailBody.innerHTML = blocks.join("");

    // Member records as table
    renderCohortMembers(snapshot.member_records || []);
  } catch (error) {
    elements.workspaceDetailTitle.textContent = "Error";
    elements.workspaceDetailMeta.textContent = error.message;
    elements.workspaceDetailBody.innerHTML = renderEmptyBlock("Snapshot unavailable", error.message);
  }
}

function renderWorkspaceMembers(members) {
  if (!members.length) {
    elements.workspaceMembersContainer.innerHTML = "";
    return;
  }

  // Preferred column order + friendly labels. Keys not in this list are
  // skipped to keep the table focused; adjust here to surface more fields.
  const MEMBER_COLUMNS = [
    { key: "experiment_name", label: "Experiment" },
    { key: "project_name", label: "Project" },
    { key: "project_type", label: "Type" },
    { key: "electrolyte", label: "Electrolyte" },
    { key: "ontology_root_batch_name", label: "Parent batch" },
    { key: "tracking_status", label: "Status" },
    { key: "experiment_date", label: "Experiment date" },
    { key: "created_date", label: "Created" },
  ];
  const sample = members[0];
  const cols = MEMBER_COLUMNS.filter((c) => c.key in sample);

  const headerCells = cols.map((c) => `<th>${escapeHtml(c.label)}</th>`).join("");
  const rows = members.slice(0, 100).map((member) => {
    const cells = cols.map((c) => {
      const val = member[c.key];
      return `<td>${escapeHtml(val != null && val !== "" ? String(val) : "—")}</td>`;
    }).join("");
    return `<tr>${cells}</tr>`;
  }).join("");

  elements.workspaceMembersContainer.innerHTML = `
    <details class="workspace-members-details">
      <summary class="workspace-members-summary">Experiments in this workspace (${members.length})</summary>
      <div class="data-table-wrap" style="max-height:420px; overflow:auto;">
        <table class="data-table">
          <thead><tr>${headerCells}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      ${members.length > 100 ? `<p style="color:var(--muted); padding:8px 4px;">Showing 100 of ${members.length} members.</p>` : ""}
    </details>
  `;
}

function renderCohortMembers(members) {
  if (!members.length) {
    elements.workspaceMembersContainer.innerHTML = renderEmptyBlock("No member records", "This snapshot has no member data.");
    return;
  }
  renderWorkspaceMembers(members);
}

function renderWorkspaceAnnotations(annotations) {
  if (!annotations.length) {
    elements.workspaceAnnotationsContainer.innerHTML = "";
    return;
  }

  elements.workspaceAnnotationsContainer.innerHTML = `
    <div class="panel-head" style="margin-top:14px">
      <h3>Annotations</h3>
      <span class="panel-subtitle">${annotations.length} note${annotations.length !== 1 ? "s" : ""}</span>
    </div>
    ${annotations.map((ann) => `
      <article class="annotation-card">
        <header>
          <div>
            <strong>${escapeHtml(ann.title || ann.annotation_type || "Note")}</strong>
            <span class="annotation-type-badge">${escapeHtml(ann.annotation_type || "NOTE")}</span>
          </div>
          <div class="annotation-actions">
            <span>${formatTimestamp(ann.created_at || ann.created_date)}</span>
            ${ann.id ? `<button class="annotation-delete-btn" data-delete-annotation-id="${ann.id}" type="button" title="Delete note">&times;</button>` : ""}
          </div>
        </header>
        <p>${escapeHtml(ann.body || ann.text || "")}</p>
      </article>
    `).join("")}
  `;
}

// =====================================================================
// Workspace Widget System
// =====================================================================

const WIDGET_Y_AXIS_PER_CYCLE = {
  capacity_retention: { label: "Capacity Retention (%)", fields: ["retention", "capacity_retention"], yrange: [60, 105] },
  coulombic_efficiency: { label: "Coulombic Efficiency (%)", fields: ["coulombic_efficiency", "ce_pct", "ce"], yrange: [80, 101] },
  discharge_capacity: { label: "Discharge Capacity (mAh/g)", fields: ["discharge_capacity", "discharge_cap_mAh_g"], yrange: null },
  charge_capacity: { label: "Charge Capacity (mAh/g)", fields: ["charge_capacity", "charge_cap_mAh_g"], yrange: null },
};

// Raw pandas column-name candidates for each semantic field. The workspace
// payload ships each cell's cycling data as a pandas DataFrame `to_json()`
// (columns orient: {"Column": {"row_idx": value}}); we parse it once per cell
// the first time a widget needs it and cache arrays on the cell object.
const CYCLE_COLUMN_CANDIDATES = ["Cycle", "Cycle number", "cycle", "cycle_number"];
const FIELD_COLUMN_MAP = {
  discharge_capacity: [
    "Q Dis (mAh/g)",
    "Q discharge (mA.h)",
    "Qdis",
    "discharge_capacity",
    "discharge_cap_mAh_g",
  ],
  charge_capacity: [
    "Q Chg (mAh/g)",
    "Q charge (mA.h)",
    "Qchg",
    "charge_capacity",
    "charge_cap_mAh_g",
  ],
  coulombic_efficiency: [
    "Efficiency (-)",
    "Efficiency",
    "CE",
    "ce",
    "coulombic_efficiency",
    "ce_pct",
  ],
};

function _columnDictToArray(col) {
  if (!col || typeof col !== "object") return null;
  const entries = Object.entries(col).map(([k, v]) => [Number(k), v]);
  entries.sort((a, b) => a[0] - b[0]);
  return entries.map(([, v]) => (v == null || v === "" ? null : Number(v)));
}

function _pickColumn(parsed, candidates) {
  for (const name of candidates) {
    if (parsed[name] != null) return parsed[name];
  }
  return null;
}

function hydrateCellCycles(cell) {
  if (!cell || cell._hydrated) return cell;
  cell._hydrated = true;
  const raw = cell.data_json;
  if (!raw) return cell;
  let parsed;
  try {
    parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch {
    return cell;
  }
  if (!parsed || typeof parsed !== "object") return cell;

  const cycles = _columnDictToArray(_pickColumn(parsed, CYCLE_COLUMN_CANDIDATES));
  if (cycles && cycles.length) cell.cycles = cycles;

  for (const [target, candidates] of Object.entries(FIELD_COLUMN_MAP)) {
    if (cell[target] != null) continue;
    const arr = _columnDictToArray(_pickColumn(parsed, candidates));
    if (arr && arr.length) cell[target] = arr;
  }

  // Efficiency in raw cycler exports is often a fraction (0.98). Convert to
  // percent when the whole series fits in [0, 1.5].
  if (Array.isArray(cell.coulombic_efficiency)) {
    const finite = cell.coulombic_efficiency.filter((v) => Number.isFinite(v));
    if (finite.length) {
      const maxCe = Math.max(...finite);
      if (maxCe <= 1.5) {
        cell.coulombic_efficiency = cell.coulombic_efficiency.map((v) =>
          v == null ? null : v * 100,
        );
      }
    }
  }

  // Derive capacity retention from discharge capacity if the backend didn't
  // ship a retention column. Normalize against the highest of the first ~5
  // non-zero discharge values (matches legacy dashboard behavior).
  if (!Array.isArray(cell.retention) && Array.isArray(cell.discharge_capacity)) {
    const dq = cell.discharge_capacity;
    const head = dq.filter((v) => Number.isFinite(v) && v > 0).slice(0, 5);
    const ref = head.length ? Math.max(...head) : 0;
    if (ref > 0) {
      cell.retention = dq.map((v) => (v == null ? null : (v / ref) * 100));
    }
  }

  return cell;
}

function hydrateCellsData(cellsData) {
  if (!Array.isArray(cellsData)) return [];
  for (const cell of cellsData) hydrateCellCycles(cell);
  return cellsData;
}

function getCellDisplayName(cell, i) {
  return cell.cell_name || cell.name || cell.cell_id || cell.test_number || `Cell ${i + 1}`;
}

const WIDGET_Y_AXIS_SUMMARY = {
  avg_retention_pct: { label: "Avg Retention (%)" },
  avg_coulombic_efficiency_pct: { label: "Avg CE (%)" },
  avg_fade_rate_pct_per_100_cycles: { label: "Fade Rate (%/100c)" },
  avg_reversible_capacity_mAh_g: { label: "Capacity (mAh/g)" },
  best_cycle_life_80: { label: "Cycle Life (80%)" },
};

function getWorkspaceWidgets(workspaceId) {
  if (!state.workspaceWidgets[workspaceId]) state.workspaceWidgets[workspaceId] = [];
  return state.workspaceWidgets[workspaceId];
}

function genWidgetId() {
  return "w_" + Math.random().toString(36).slice(2, 9);
}

function renderWorkspaceCanvas() {
  const plots = state.workspaceDetail?.plots || {};
  const workspaceId = state.selectedWorkspaceId;
  if (!workspaceId || !elements.widgetCanvas) return;

  const cellsData = hydrateCellsData(plots.cells_data || []);
  const metricRows = plots.metric_rows || [];
  const members = state.workspaceDetail?.members || [];
  const hasData = cellsData.length > 0 || metricRows.length > 0;

  if (hasData) {
    elements.widgetCanvas.hidden = false;
    if (elements.wGroupCount) {
      elements.wGroupCount.textContent = `${cellsData.length} cell${cellsData.length !== 1 ? "s" : ""}`;
    }
  } else {
    elements.widgetCanvas.hidden = true;
  }

  renderWidgetGrid(workspaceId);
}

function renderWidgetGrid(workspaceId) {
  if (!elements.widgetGrid) return;
  const widgets = getWorkspaceWidgets(workspaceId);
  const plots = state.workspaceDetail?.plots || {};

  if (!widgets.length) {
    elements.widgetGrid.innerHTML = `
      <div class="widget-empty-state">
        <p>No widgets yet. Click <strong>+ Add Widget</strong> to create your first analysis chart.</p>
      </div>`;
    return;
  }

  // Purge stale Plotly instances
  elements.widgetGrid.querySelectorAll(".widget-plot-target").forEach((el) => {
    if (window.Plotly) Plotly.purge(el);
  });

  elements.widgetGrid.innerHTML = widgets.map((w) => `
    <div class="widget-card" data-widget-id="${w.id}">
      <div class="widget-card-header">
        <div class="widget-card-title">
          <span class="widget-type-badge">${w.type === "line" ? "Line" : w.type === "bar" ? "Bar" : w.type === "scatter" ? "Scatter" : "Box"}</span>
          <span class="widget-title-text">${escapeHtml(w.title)}</span>
        </div>
        <div class="widget-card-actions">
          <button class="widget-action-btn" data-edit-widget="${w.id}" title="Edit widget">&#x270E;</button>
          <button class="widget-action-btn widget-action-btn--danger" data-delete-widget="${w.id}" title="Remove widget">&times;</button>
        </div>
      </div>
      <div class="widget-card-meta">
        <span class="widget-meta-tag">${w.dataType === "per_cycle" ? "Per-Cycle" : "Summary"}</span>
        <span class="widget-meta-tag">${getYAxisLabel(w)}</span>
        ${w.groupBy ? `<span class="widget-meta-tag">by ${w.groupBy}</span>` : ""}
      </div>
      <div class="widget-plot-target" id="plot_${w.id}" style="min-height:260px"></div>
    </div>
  `).join("");

  // Render charts for all widgets
  if (window.Plotly) {
    for (const w of widgets) {
      const plotTarget = document.getElementById(`plot_${w.id}`);
      if (plotTarget) renderWidgetChart(w, plots, plotTarget);
    }
  }
}

function getYAxisLabel(widget) {
  if (widget.dataType === "per_cycle") {
    return WIDGET_Y_AXIS_PER_CYCLE[widget.yAxis]?.label || widget.yAxis;
  }
  return WIDGET_Y_AXIS_SUMMARY[widget.yAxis]?.label || widget.yAxis;
}

function getFieldValue(cell, fields) {
  if (!Array.isArray(fields)) return cell[fields] || null;
  for (const f of fields) {
    if (cell[f] != null) return cell[f];
  }
  return null;
}

function renderWidgetChart(widget, plots, container) {
  const cellsData = plots.cells_data || [];
  const metricRows = plots.metric_rows || [];
  const members = state.workspaceDetail?.members || [];

  if (widget.dataType === "per_cycle") {
    renderPerCycleWidget(widget, cellsData, members, container);
  } else {
    renderSummaryWidget(widget, metricRows, members, container);
  }
}

function renderPerCycleWidget(widget, cellsData, members, container) {
  if (!cellsData.length) {
    container.innerHTML = renderEmptyBlock("No per-cycle data", "This workspace has no per-cycle cell data.");
    return;
  }

  // Make sure raw data_json is parsed into per-field arrays (idempotent).
  hydrateCellsData(cellsData);

  const yMeta = WIDGET_Y_AXIS_PER_CYCLE[widget.yAxis] || WIDGET_Y_AXIS_PER_CYCLE.capacity_retention;
  const cycleFilter = parseCycleFilter(widget.cycleFilter);

  // Build experiment -> color map for grouping
  const groupMap = buildGroupMap(cellsData, members, widget.groupBy);

  const traces = cellsData.slice(0, 30).map((cell, i) => {
    const name = getCellDisplayName(cell, i);
    let xs = cell.cycles || cell.cycle_numbers || [];
    let ys = getFieldValue(cell, yMeta.fields) || [];

    if (!Array.isArray(ys) || !ys.length) return null;
    if (!Array.isArray(xs) || !xs.length) {
      // Fall back to 1..N if there's no explicit cycle column but we have Y values.
      xs = ys.map((_, j) => j + 1);
    }

    // Drop rows where either coordinate is null/NaN so Plotly renders a clean line.
    const pairsAll = xs.map((x, j) => [x, ys[j]]).filter(
      ([x, y]) => Number.isFinite(x) && Number.isFinite(y),
    );

    const pairs = cycleFilter && (cycleFilter.min != null || cycleFilter.max != null)
      ? pairsAll.filter(([x]) =>
          (cycleFilter.min == null || x >= cycleFilter.min) &&
          (cycleFilter.max == null || x <= cycleFilter.max),
        )
      : pairsAll;

    if (!pairs.length) return null;
    xs = pairs.map(([x]) => x);
    ys = pairs.map(([, y]) => y);

    const color = groupMap[name] || GROUP_PALETTE[i % GROUP_PALETTE.length];

    return {
      x: xs, y: ys, name,
      mode: "lines",
      type: "scatter",
      line: { color, width: 1.5 },
      hovertemplate: `${escapeHtml(String(name))}<br>Cycle: %{x}<br>${yMeta.label}: %{y:.2f}<extra></extra>`,
    };
  }).filter(Boolean);

  if (!traces.length) {
    container.innerHTML = renderEmptyBlock("No data", "Selected metric has no values in this workspace.");
    return;
  }

  const layout = {
    ...PLOTLY_BASE_LAYOUT,
    xaxis: { ...PLOTLY_BASE_LAYOUT.xaxis, title: "Cycle Number" },
    yaxis: { ...PLOTLY_BASE_LAYOUT.yaxis, title: yMeta.label, ...(yMeta.yrange ? { range: yMeta.yrange } : {}) },
    showlegend: traces.length > 1,
    legend: { orientation: "h", y: -0.25, font: { size: 10 } },
    margin: { t: 16, r: 30, b: traces.length > 1 ? 80 : 50, l: 60 },
  };

  Plotly.newPlot(container, traces, layout, PLOTLY_CONFIG);
}

function renderSummaryWidget(widget, metricRows, members, container) {
  if (!metricRows.length) {
    container.innerHTML = renderEmptyBlock("No summary data", "This workspace has no per-experiment metrics.");
    return;
  }

  const yMeta = WIDGET_Y_AXIS_SUMMARY[widget.yAxis] || WIDGET_Y_AXIS_SUMMARY.avg_retention_pct;
  const rows = metricRows.filter((r) => r[widget.yAxis] != null);

  if (!rows.length) {
    container.innerHTML = renderEmptyBlock("No data", "Selected metric has no values in this workspace.");
    return;
  }

  const groups = buildSummaryGroups(rows, widget.groupBy);
  const groupNames = Object.keys(groups);
  const isGrouped = widget.groupBy && groupNames.length > 1;

  const traces = [];

  if (widget.type === "box") {
    groupNames.forEach((gName, i) => {
      const vals = groups[gName].map((r) => r[widget.yAxis]).filter((v) => v != null);
      const names = groups[gName].map((r) => r.experiment_name);
      if (!vals.length) return;
      const c = GROUP_PALETTE[i % GROUP_PALETTE.length];
      traces.push({
        y: vals, text: names, name: gName, type: "box",
        boxpoints: "all", jitter: 0.3, pointpos: -1.5,
        marker: { color: c, size: 5 }, line: { color: c },
        fillcolor: c + "20",
        hovertemplate: "%{text}<br>%{y:.2f}<extra>" + escapeHtml(gName) + "</extra>",
      });
    });
  } else if (widget.type === "bar") {
    groupNames.forEach((gName, i) => {
      const c = GROUP_PALETTE[i % GROUP_PALETTE.length];
      const gRows = groups[gName];
      traces.push({
        x: gRows.map((r) => r.experiment_name || r.experiment_id),
        y: gRows.map((r) => r[widget.yAxis]),
        name: gName,
        type: "bar",
        marker: { color: c },
        hovertemplate: "%{x}<br>" + yMeta.label + ": %{y:.2f}<extra>" + escapeHtml(gName) + "</extra>",
      });
    });
  } else {
    // Default: scatter
    groupNames.forEach((gName, i) => {
      const c = GROUP_PALETTE[i % GROUP_PALETTE.length];
      const gRows = groups[gName];
      traces.push({
        x: gRows.map((r) => r.experiment_name || r.experiment_id),
        y: gRows.map((r) => r[widget.yAxis]),
        name: gName,
        type: "scatter",
        mode: "markers",
        marker: { color: c, size: 9, opacity: 0.85 },
        hovertemplate: "%{x}<br>" + yMeta.label + ": %{y:.2f}<extra>" + escapeHtml(gName) + "</extra>",
      });
    });
  }

  if (!traces.length) {
    container.innerHTML = renderEmptyBlock("No data", "Insufficient data for this widget.");
    return;
  }

  Plotly.newPlot(container, traces, {
    ...PLOTLY_BASE_LAYOUT,
    yaxis: { ...PLOTLY_BASE_LAYOUT.yaxis, title: yMeta.label },
    xaxis: { ...PLOTLY_BASE_LAYOUT.xaxis, automargin: true, tickangle: -30 },
    barmode: "group",
    showlegend: isGrouped,
    legend: { orientation: "h", y: -0.25, font: { size: 10 } },
    margin: { t: 16, r: 30, b: 80, l: 60 },
  }, PLOTLY_CONFIG);
}

function buildGroupMap(cellsData, members, groupBy) {
  if (!groupBy) return {};

  // Resolve each cell's grouping key, then assign a stable color per group.
  const expMemberByName = {};
  for (const m of members) {
    const expName = m.experiment_name || m.name;
    if (expName) expMemberByName[expName] = m;
  }

  const groupKeyFor = (cell) => {
    const expName = cell.experiment_name;
    const member = (expName && expMemberByName[expName]) || {};
    if (groupBy === "experiment") return expName || "Unknown";
    if (groupBy === "project") return cell.project_name || member.project_name || "Unknown";
    if (groupBy === "electrolyte") return cell.electrolyte || member.electrolyte || "Unknown";
    return "Unknown";
  };

  const groupColor = {};
  const map = {};
  cellsData.forEach((cell, i) => {
    const name = getCellDisplayName(cell, i);
    const key = groupKeyFor(cell);
    if (!(key in groupColor)) {
      groupColor[key] = GROUP_PALETTE[Object.keys(groupColor).length % GROUP_PALETTE.length];
    }
    map[name] = groupColor[key];
  });
  return map;
}

function buildSummaryGroups(rows, groupBy) {
  if (!groupBy) return { All: rows };
  const groups = {};
  for (const r of rows) {
    let key = "Unknown";
    if (groupBy === "experiment") key = r.experiment_name || String(r.experiment_id);
    else if (groupBy === "project") key = r.project_name || "Unknown";
    else if (groupBy === "electrolyte") key = r.electrolyte || "Unknown";
    if (!groups[key]) groups[key] = [];
    groups[key].push(r);
  }
  return Object.keys(groups).length ? groups : { All: rows };
}

function parseCycleFilter(cycleFilter) {
  if (!cycleFilter) return null;
  const min = cycleFilter.min != null ? Number(cycleFilter.min) : null;
  const max = cycleFilter.max != null ? Number(cycleFilter.max) : null;
  return { min: isNaN(min) ? null : min, max: isNaN(max) ? null : max };
}

// --- Sidebar management ---

function openNewWidgetSidebar() {
  state.workspaceActiveWidgetId = null;
  resetWidgetSidebar();
  showManageWidgetsSidebar();
}

function openEditWidgetSidebar(widgetId) {
  const workspaceId = state.selectedWorkspaceId;
  if (!workspaceId) return;
  const widget = getWorkspaceWidgets(workspaceId).find((w) => w.id === widgetId);
  if (!widget) return;

  state.workspaceActiveWidgetId = widgetId;
  populateWidgetSidebar(widget);
  showManageWidgetsSidebar();
}

function showManageWidgetsSidebar() {
  if (!elements.manageWidgetsSidebar) return;
  elements.manageWidgetsSidebar.hidden = false;
  syncWidgetSidebarToDataType();
  schedulePlotlyResize();
}

function closeManageWidgetsSidebar() {
  if (elements.manageWidgetsSidebar) elements.manageWidgetsSidebar.hidden = true;
  state.workspaceActiveWidgetId = null;
  schedulePlotlyResize();
}

// When the right-edge drawer opens/closes, widget canvas width changes. Nudge
// Plotly to reflow after the CSS transition completes.
function schedulePlotlyResize() {
  if (!window.Plotly || !elements.widgetGrid) return;
  setTimeout(() => {
    elements.widgetGrid.querySelectorAll(".widget-plot-target").forEach((el) => {
      try { Plotly.Plots.resize(el); } catch { /* noop */ }
    });
  }, 60);
}

function resetWidgetSidebar() {
  if (elements.wWidgetType) elements.wWidgetType.value = "line";
  if (elements.wDataType) elements.wDataType.value = "per_cycle";
  if (elements.wGroupBy) elements.wGroupBy.value = "";
  if (elements.wXAxis) elements.wXAxis.value = "cycle_number";
  if (elements.wYAxis) elements.wYAxis.value = "capacity_retention";
  if (elements.wFiltersList) elements.wFiltersList.innerHTML = "";
  if (elements.wCycleSelectorList) elements.wCycleSelectorList.innerHTML = "";
}

function populateWidgetSidebar(widget) {
  if (elements.wWidgetType) elements.wWidgetType.value = widget.type || "line";
  if (elements.wDataType) elements.wDataType.value = widget.dataType || "per_cycle";
  if (elements.wGroupBy) elements.wGroupBy.value = widget.groupBy || "";
  if (elements.wYAxis) elements.wYAxis.value = widget.yAxis || "capacity_retention";
  if (elements.wFiltersList) elements.wFiltersList.innerHTML = "";
  if (elements.wCycleSelectorList) {
    elements.wCycleSelectorList.innerHTML = "";
    if (widget.cycleFilter) {
      addWidgetCycleSelectorRow(widget.cycleFilter.min, widget.cycleFilter.max);
    }
  }
}

function syncWidgetSidebarToDataType() {
  const dataType = elements.wDataType?.value || "per_cycle";

  // Swap Y-axis options
  if (elements.wYAxis) {
    const current = elements.wYAxis.value;
    const opts = dataType === "per_cycle" ? WIDGET_Y_AXIS_PER_CYCLE : WIDGET_Y_AXIS_SUMMARY;
    elements.wYAxis.innerHTML = Object.entries(opts)
      .map(([k, v]) => `<option value="${k}"${k === current ? " selected" : ""}>${escapeHtml(v.label)}</option>`)
      .join("");
  }

  // X-axis for summary is always "experiment"
  if (elements.wXAxisWrap) {
    if (dataType === "summary") {
      elements.wXAxisWrap.style.display = "none";
    } else {
      elements.wXAxisWrap.style.display = "";
    }
  }
}

function addWidgetFilterRow() {
  if (!elements.wFiltersList) return;
  const row = document.createElement("div");
  row.className = "mw-filter-row";
  row.innerHTML = `
    <select class="mw-select mw-filter-field">
      <option value="project">Project</option>
      <option value="electrolyte">Electrolyte</option>
    </select>
    <input type="text" class="mw-filter-value mw-select" placeholder="Value…" />
    <button class="mw-remove-btn" type="button">&times;</button>
  `;
  row.querySelector(".mw-remove-btn").addEventListener("click", () => row.remove());
  elements.wFiltersList.append(row);
}

function addWidgetCycleSelectorRow(minVal = "", maxVal = "") {
  if (!elements.wCycleSelectorList) return;
  elements.wCycleSelectorList.innerHTML = "";
  const row = document.createElement("div");
  row.className = "mw-cycle-row";
  row.innerHTML = `
    <div class="mw-cycle-inputs">
      <div class="mw-field-wrap" style="flex:1">
        <label class="mw-field-label">Min Cycle</label>
        <input id="wCycleMin" type="number" class="mw-select" placeholder="e.g. 1" min="1" value="${minVal}" />
      </div>
      <div class="mw-field-wrap" style="flex:1">
        <label class="mw-field-label">Max Cycle</label>
        <input id="wCycleMax" type="number" class="mw-select" placeholder="e.g. 500" min="1" value="${maxVal}" />
      </div>
    </div>
    <button class="mw-remove-btn" type="button" style="margin-top:4px">&times; Remove</button>
  `;
  row.querySelector(".mw-remove-btn").addEventListener("click", () => {
    elements.wCycleSelectorList.innerHTML = "";
  });
  elements.wCycleSelectorList.append(row);
}

function readWidgetSidebar() {
  const type = elements.wWidgetType?.value || "line";
  const dataType = elements.wDataType?.value || "per_cycle";
  const groupBy = elements.wGroupBy?.value || "";
  const yAxis = elements.wYAxis?.value || "capacity_retention";

  // Cycle filter
  let cycleFilter = null;
  const minInput = elements.wCycleSelectorList?.querySelector("#wCycleMin");
  const maxInput = elements.wCycleSelectorList?.querySelector("#wCycleMax");
  if (minInput || maxInput) {
    const min = minInput?.value ? Number(minInput.value) : null;
    const max = maxInput?.value ? Number(maxInput.value) : null;
    if (min != null || max != null) cycleFilter = { min, max };
  }

  const yOpts = dataType === "per_cycle" ? WIDGET_Y_AXIS_PER_CYCLE : WIDGET_Y_AXIS_SUMMARY;
  const yLabel = yOpts[yAxis]?.label || yAxis;

  return { type, dataType, groupBy, yAxis, cycleFilter, title: yLabel };
}

function generateActiveWidget() {
  const workspaceId = state.selectedWorkspaceId;
  if (!workspaceId) return;

  const config = readWidgetSidebar();
  const widgets = getWorkspaceWidgets(workspaceId);

  if (state.workspaceActiveWidgetId) {
    const idx = widgets.findIndex((w) => w.id === state.workspaceActiveWidgetId);
    if (idx >= 0) widgets[idx] = { ...widgets[idx], ...config };
  } else {
    widgets.push({ id: genWidgetId(), ...config });
  }

  closeManageWidgetsSidebar();
  renderWidgetGrid(workspaceId);
}

function deleteWidget(widgetId) {
  const workspaceId = state.selectedWorkspaceId;
  if (!workspaceId) return;
  state.workspaceWidgets[workspaceId] = getWorkspaceWidgets(workspaceId).filter((w) => w.id !== widgetId);
  renderWidgetGrid(workspaceId);
}

// =====================================================================
// Workspace Mutations
// =====================================================================

async function openSnapshotAsWorkspace() {
  const snapshotId = state.selectedCohortSnapshotId;
  if (!snapshotId) return;

  await withButtonBusy(elements.openAsWorkspaceButton, async () => {
    const result = await api.createStudyWorkspace({ snapshot_id: snapshotId });
    showToast(result.created ? "Workspace created." : "Existing workspace opened.", "success");
    await loadStudyWorkspaces();
    state.selectedCohortSnapshotId = null;
    await selectWorkspace(result.workspace_id);
  });
}

async function deleteCurrentWorkspace() {
  const workspaceId = state.selectedWorkspaceId;
  if (!workspaceId) return;
  if (!confirm("Delete this workspace and all its annotations? This cannot be undone.")) return;

  await withButtonBusy(elements.deleteWorkspaceButton, async () => {
    await api.deleteStudyWorkspace(workspaceId);
    showToast("Workspace deleted.", "success");
    state.selectedWorkspaceId = null;
    state.workspaceDetail = null;
    if (elements.workspaceActions) elements.workspaceActions.hidden = true;
    if (elements.workspaceAnnotationFormContainer) elements.workspaceAnnotationFormContainer.hidden = true;
    elements.workspaceDetailTitle.textContent = "Select a workspace or cohort";
    elements.workspaceDetailMeta.textContent = "Details appear here";
    elements.workspaceDetailBody.innerHTML = '<div class="empty-state">Choose a workspace or cohort snapshot from the list.</div>';
    elements.workspaceMembersContainer.innerHTML = "";
    if (elements.widgetCanvas) elements.widgetCanvas.hidden = true;
    if (elements.manageWidgetsSidebar) elements.manageWidgetsSidebar.hidden = true;
    elements.workspaceAnnotationsContainer.innerHTML = "";
    await loadStudyWorkspaces();
  });
}

async function submitWorkspaceAnnotation() {
  const workspaceId = state.selectedWorkspaceId;
  if (!workspaceId) return;

  const body = elements.annotationBody?.value?.trim();
  if (!body) return;

  const payload = {
    body,
    title: elements.annotationTitle?.value?.trim() || null,
    annotation_type: elements.annotationType?.value || "NOTE",
  };

  await withFormBusy(elements.workspaceAnnotationForm, async () => {
    await api.createWorkspaceAnnotation(workspaceId, payload);
    showToast("Note saved.", "success");
    elements.workspaceAnnotationForm.reset();
    // Reload workspace to get updated annotations
    const updated = await api.getStudyWorkspace(workspaceId);
    state.workspaceDetail = updated;
    renderWorkspaceAnnotations(updated.annotations || []);
    await loadStudyWorkspaces(); // refresh annotation count
  });
}

async function deleteAnnotation(annotationId) {
  if (!annotationId || !state.selectedWorkspaceId) return;
  if (!confirm("Delete this note?")) return;

  await api.deleteWorkspaceAnnotation(annotationId);
  showToast("Note deleted.", "success");
  const updated = await api.getStudyWorkspace(state.selectedWorkspaceId);
  state.workspaceDetail = updated;
  renderWorkspaceAnnotations(updated.annotations || []);
  await loadStudyWorkspaces();
}

// =====================================================================
// Search & Filter (Workspaces sub-tab)
// =====================================================================

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

function switchWorkspacesTab(tab) {
  state.sfActiveTab = tab;
  document.querySelectorAll("#workspacesSubNav .sub-nav-tab").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.wsTab === tab);
  });
  if (elements.wsPaneMy) elements.wsPaneMy.hidden = tab !== "my";
  if (elements.wsPaneSearch) elements.wsPaneSearch.hidden = tab !== "search";
  if (tab === "search" && !state.sfLoaded) {
    loadSfData();
  }
}

async function loadSfData() {
  if (elements.sfResultsCount) elements.sfResultsCount.textContent = "Loading experiments…";
  try {
    const data = await api.getCohortRecords();
    state.cohortRecords = data.records || [];
    state.cohortFilterOptions = data.filter_options || {};
    state.sfLoaded = true;
    applySfFilters();
  } catch (error) {
    if (elements.sfResultsCount) elements.sfResultsCount.textContent = `Error: ${error.message}`;
    if (elements.sfResultsTableContainer) {
      elements.sfResultsTableContainer.innerHTML = renderEmptyBlock("Unable to load experiments", error.message);
    }
  }
}

// Attributes covered by each checkbox filter section. Used to generate live
// match-count badges while respecting *other* active filter dimensions.
const SF_FILTER_ATTR = {
  projectIds: "project_id",
  rootBatches: "ontology_root_batch_name",
  electrolytes: "electrolyte",
  statuses: "tracking_status",
};

function populateSfFilters() {
  const opts = state.cohortFilterOptions;

  const renderChecks = (el, items, filterKey, options = {}) => {
    if (!el) return;
    const { searchable = false } = options;
    if (!items.length) {
      el.innerHTML = '<p class="sf-filter-empty">None available</p>';
      return;
    }
    const selected = state.sfFilters[filterKey];
    const matchingCounts = computeSfMatchingCounts(filterKey);
    const searchTerm = state.sfFilterSearch[filterKey] || "";
    const searchHeader = searchable
      ? `<div class="sf-filter-search-wrap">
          <input type="search" class="sf-filter-search" data-sf-filter-search="${filterKey}"
                 value="${escapeHtml(searchTerm)}" placeholder="Search…" />
        </div>`
      : "";
    const body = items.map((item) => {
      const label = typeof item === "object" ? item.label : item;
      const value = typeof item === "object" ? item.id : item;
      const checked = selected.has(String(value)) || selected.has(value);
      const count = matchingCounts.get(String(value)) ?? 0;
      const labelLower = String(label).toLowerCase();
      const hidden = searchTerm && !labelLower.includes(searchTerm);
      const cls = [
        "sf-check",
        count === 0 && !checked ? "is-zero" : "",
        hidden ? "is-hidden" : "",
      ].filter(Boolean).join(" ");
      return `<label class="${cls}">
        <input type="checkbox" data-sf-filter="${filterKey}" value="${escapeHtml(String(value))}" ${checked ? "checked" : ""} />
        <span class="sf-check-label">${escapeHtml(String(label))}</span>
        <span class="sf-check-count">(${count})</span>
      </label>`;
    }).join("");
    el.innerHTML = searchHeader + body;
  };

  renderChecks(elements.sfProjectFilter, opts.project_options || [], "projectIds", { searchable: true });
  renderChecks(elements.sfBatchFilter, (opts.ontology_root_batch_names || []).map((n) => ({ id: n, label: n })), "rootBatches", { searchable: true });
  renderChecks(elements.sfElectrolyteFilter, (opts.electrolytes || []).map((n) => ({ id: n, label: n })), "electrolytes", { searchable: true });
  renderChecks(elements.sfStatusFilter, (opts.tracking_statuses || []).map((n) => ({ id: n, label: n })), "statuses", { searchable: true });

  if (elements.sfAccordion && !elements.sfAccordion.dataset.sfWired) {
    elements.sfAccordion.addEventListener("change", (event) => {
      const cb = event.target.closest('input[type="checkbox"][data-sf-filter]');
      if (!cb) return;
      const key = cb.dataset.sfFilter;
      const setRef = state.sfFilters[key];
      const val = key === "projectIds" ? Number(cb.value) : cb.value;
      if (cb.checked) setRef.add(val);
      else setRef.delete(val);
      applySfFilters();
    });
    elements.sfAccordion.dataset.sfWired = "1";
  }

  updateSfAccordionCounts();
}

function computeSfMatchingCounts(excludeKey) {
  // For the filter section identified by `excludeKey`, count how many records
  // would match each possible value if that dimension were the *only* change.
  // We apply every other active filter, then bucket the remaining records by
  // this section's attribute.
  const attr = SF_FILTER_ATTR[excludeKey];
  const counts = new Map();
  if (!attr) return counts;
  const f = state.sfFilters;
  const search = (f.search || "").toLowerCase();
  for (const r of state.cohortRecords) {
    if (excludeKey !== "projectIds" && f.projectIds.size && !f.projectIds.has(r.project_id)) continue;
    if (excludeKey !== "rootBatches" && f.rootBatches.size && !f.rootBatches.has(r.ontology_root_batch_name)) continue;
    if (excludeKey !== "electrolytes" && f.electrolytes.size && !f.electrolytes.has(r.electrolyte)) continue;
    if (excludeKey !== "statuses" && f.statuses.size && !f.statuses.has(r.tracking_status)) continue;
    if (f.minRetention != null && (r.avg_retention_pct == null || r.avg_retention_pct < f.minRetention)) continue;
    if (f.minCE != null && (r.avg_coulombic_efficiency_pct == null || r.avg_coulombic_efficiency_pct < f.minCE)) continue;
    if (f.maxFade != null && (r.avg_fade_rate_pct_per_100_cycles == null || r.avg_fade_rate_pct_per_100_cycles > f.maxFade)) continue;
    if (f.minCycleLife != null && (r.best_cycle_life_80 == null || r.best_cycle_life_80 < f.minCycleLife)) continue;
    if (!recordMatchesDateRange(r, f.dateFrom, f.dateTo)) continue;
    if (search) {
      const haystack = [r.experiment_name, r.project_name, r.electrolyte, r.ontology_root_batch_name]
        .filter(Boolean).join(" ").toLowerCase();
      if (!haystack.includes(search)) continue;
    }
    const raw = r[attr];
    if (raw == null || raw === "") continue;
    const key = String(raw);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return counts;
}

function recordMatchesDateRange(record, from, to) {
  if (!from && !to) return true;
  const raw = record.experiment_date || record.created_date;
  if (!raw) return !from && !to;
  // Accept YYYY-MM-DD or ISO strings; lexicographic compare on leading 10 chars.
  const day = String(raw).slice(0, 10);
  if (from && day < from) return false;
  if (to && day > to) return false;
  return true;
}

function applySfFilterSectionSearch(filterKey) {
  const container = {
    projectIds: elements.sfProjectFilter,
    rootBatches: elements.sfBatchFilter,
    electrolytes: elements.sfElectrolyteFilter,
    statuses: elements.sfStatusFilter,
  }[filterKey];
  if (!container) return;
  const term = state.sfFilterSearch[filterKey] || "";
  container.querySelectorAll(".sf-check").forEach((row) => {
    const lbl = row.querySelector(".sf-check-label");
    const text = (lbl?.textContent || "").toLowerCase();
    row.classList.toggle("is-hidden", Boolean(term) && !text.includes(term));
  });
}

function updateSfAccordionCounts() {
  const countEl = (el, n) => { if (el) el.textContent = n ? `(${n})` : ""; };
  countEl(elements.sfProjectCount, state.sfFilters.projectIds.size);
  countEl(elements.sfBatchCount, state.sfFilters.rootBatches.size);
  countEl(elements.sfElectrolyteCount, state.sfFilters.electrolytes.size);
  countEl(elements.sfStatusCount, state.sfFilters.statuses.size);
  const dateActive = Number(Boolean(state.sfFilters.dateFrom)) + Number(Boolean(state.sfFilters.dateTo));
  countEl(elements.sfDateCount, dateActive);
}

function applySfFilters() {
  const f = state.sfFilters;
  const search = f.search.toLowerCase();
  const filtered = state.cohortRecords.filter((r) => {
    if (f.projectIds.size && !f.projectIds.has(r.project_id)) return false;
    if (f.rootBatches.size && !f.rootBatches.has(r.ontology_root_batch_name)) return false;
    if (f.electrolytes.size && !f.electrolytes.has(r.electrolyte)) return false;
    if (f.statuses.size && !f.statuses.has(r.tracking_status)) return false;
    if (f.minRetention != null && (r.avg_retention_pct == null || r.avg_retention_pct < f.minRetention)) return false;
    if (f.minCE != null && (r.avg_coulombic_efficiency_pct == null || r.avg_coulombic_efficiency_pct < f.minCE)) return false;
    if (f.maxFade != null && (r.avg_fade_rate_pct_per_100_cycles == null || r.avg_fade_rate_pct_per_100_cycles > f.maxFade)) return false;
    if (f.minCycleLife != null && (r.best_cycle_life_80 == null || r.best_cycle_life_80 < f.minCycleLife)) return false;
    if (!recordMatchesDateRange(r, f.dateFrom, f.dateTo)) return false;
    if (search) {
      const haystack = [r.experiment_name, r.project_name, r.electrolyte, r.ontology_root_batch_name]
        .filter(Boolean).join(" ").toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
  state.sfFilteredRecords = filtered;
  populateSfFilters();
  renderSfResults();
  updateSfSelectionUi();
}

function renderSfResults() {
  if (!elements.sfResultsTableContainer) return;
  const records = state.sfFilteredRecords;
  const total = records.length;

  if (elements.sfResultsCount) {
    elements.sfResultsCount.textContent = `${total} experiment${total !== 1 ? "s" : ""}`;
  }

  if (!total) {
    elements.sfResultsTableContainer.innerHTML = renderEmptyBlock("No matches", "Adjust filters to include more experiments.");
    return;
  }

  const visible = state.sfColumnsVisible || {};
  const cols = SF_COLUMN_DEFS.filter((c) => c.alwaysVisible || visible[c.key] !== false);

  const allSelected = records.every((r) => state.sfSelectedIds.has(r.experiment_id));
  const someSelected = !allSelected && records.some((r) => state.sfSelectedIds.has(r.experiment_id));

  const headerCells = cols.map((c) => `<th>${escapeHtml(c.label)}</th>`).join("");
  const bodyRows = records.map((r) => {
    const cells = cols.map((c) => {
      const val = c.fmt ? c.fmt(r[c.key]) : (r[c.key] ?? "—");
      return `<td>${escapeHtml(String(val))}</td>`;
    }).join("");
    const checked = state.sfSelectedIds.has(r.experiment_id) ? "checked" : "";
    return `<tr class="sf-row ${checked ? "is-selected" : ""}" data-sf-row-id="${r.experiment_id}">
      <td class="sf-check-cell"><input type="checkbox" data-sf-row="${r.experiment_id}" ${checked} /></td>
      ${cells}
    </tr>`;
  }).join("");

  elements.sfResultsTableContainer.innerHTML = `
    <div class="sf-table-wrap">
      <table class="data-table sf-results-table">
        <thead>
          <tr>
            <th class="sf-check-cell">
              <input type="checkbox" data-sf-select-all ${allSelected ? "checked" : ""} />
            </th>
            ${headerCells}
          </tr>
        </thead>
        <tbody>${bodyRows}</tbody>
      </table>
    </div>
  `;

  const selectAllEl = elements.sfResultsTableContainer.querySelector('input[data-sf-select-all]');
  if (selectAllEl) selectAllEl.indeterminate = someSelected;
}

function updateSfSelectionUi() {
  const count = state.sfSelectedIds.size;
  if (elements.sfSelectionCount) {
    elements.sfSelectionCount.textContent = `${count} selected`;
    elements.sfSelectionCount.classList.toggle("is-active", count > 0);
  }
  if (elements.sfCreateWorkspaceBtn) elements.sfCreateWorkspaceBtn.disabled = count === 0;
  if (elements.sfClearSelectionBtn) elements.sfClearSelectionBtn.hidden = count === 0;
  if (!count && elements.sfCreateForm) elements.sfCreateForm.hidden = true;
}

function resetSfFilters() {
  state.sfFilters.projectIds.clear();
  state.sfFilters.rootBatches.clear();
  state.sfFilters.electrolytes.clear();
  state.sfFilters.statuses.clear();
  state.sfFilters.search = "";
  state.sfFilters.minRetention = null;
  state.sfFilters.minCE = null;
  state.sfFilters.maxFade = null;
  state.sfFilters.minCycleLife = null;
  state.sfFilters.dateFrom = "";
  state.sfFilters.dateTo = "";
  Object.keys(state.sfFilterSearch).forEach((k) => { state.sfFilterSearch[k] = ""; });
  if (elements.sfSearchInput) elements.sfSearchInput.value = "";
  [elements.sfMinRetention, elements.sfMinCE, elements.sfMaxFade, elements.sfMinCycleLife,
   elements.sfDateFrom, elements.sfDateTo]
    .forEach((el) => { if (el) el.value = ""; });
  populateSfFilters();
  applySfFilters();
}

// --- Results column picker ---

function persistSfColumnsVisible() {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(SF_COLUMNS_STORAGE_KEY, JSON.stringify(state.sfColumnsVisible));
  } catch {
    // storage unavailable; silently ignore
  }
}

function toggleSfColumnsMenu() {
  if (!elements.sfColumnsMenu || !elements.sfColumnsBtn) return;
  const isOpen = !elements.sfColumnsMenu.hidden;
  if (isOpen) {
    closeSfColumnsMenu();
  } else {
    renderSfColumnsMenu();
    elements.sfColumnsMenu.hidden = false;
    elements.sfColumnsBtn.setAttribute("aria-expanded", "true");
  }
}

function closeSfColumnsMenu() {
  if (!elements.sfColumnsMenu || !elements.sfColumnsBtn) return;
  elements.sfColumnsMenu.hidden = true;
  elements.sfColumnsBtn.setAttribute("aria-expanded", "false");
}

function renderSfColumnsMenu() {
  if (!elements.sfColumnsMenu) return;
  const visible = state.sfColumnsVisible || {};
  const rows = SF_COLUMN_DEFS
    .filter((c) => !c.alwaysVisible)
    .map((c) => {
      const checked = visible[c.key] !== false ? "checked" : "";
      return `<label class="sf-check">
        <input type="checkbox" data-sf-col="${c.key}" ${checked} />
        <span class="sf-check-label">${escapeHtml(c.label)}</span>
      </label>`;
    }).join("");
  elements.sfColumnsMenu.innerHTML = `
    <div class="sf-col-picker-menu-head">Visible columns</div>
    ${rows}
  `;
}

async function createWorkspaceFromSelection() {
  const name = elements.sfWorkspaceName?.value?.trim();
  if (!name) {
    showToast("Enter a name for the workspace.", "error");
    elements.sfWorkspaceName?.focus();
    return;
  }
  const ids = [...state.sfSelectedIds];
  if (!ids.length) return;

  const description = elements.sfWorkspaceDesc?.value?.trim() || null;
  const filters = { experiment_ids: ids };

  await withButtonBusy(elements.sfConfirmCreateBtn, async () => {
    try {
      const snapshot = await api.createCohortSnapshot({ name, description, filters });
      const snapshotId = snapshot.id ?? snapshot.snapshot_id ?? snapshot.cohort_snapshot_id;
      const workspace = await api.createStudyWorkspace({ snapshot_id: snapshotId });
      showToast(`Workspace "${name}" created.`, "success");

      // Reset form + selection
      if (elements.sfWorkspaceName) elements.sfWorkspaceName.value = "";
      if (elements.sfWorkspaceDesc) elements.sfWorkspaceDesc.value = "";
      if (elements.sfCreateForm) elements.sfCreateForm.hidden = true;
      state.sfSelectedIds.clear();
      renderSfResults();
      updateSfSelectionUi();

      // Refresh lists and switch to My Workspaces with the new one selected
      await loadCohortSnapshots();
      await loadStudyWorkspaces();
      switchWorkspacesTab("my");
      if (workspace?.workspace_id) {
        await selectWorkspace(workspace.workspace_id);
      }
    } catch (error) {
      showToast(`Error: ${error.message}`, "error");
    }
  });
}

// =====================================================================
// Master Table — Project-wide data grid
// =====================================================================

const MASTER_TABLE_COLS = [
  // Always-visible info columns
  { key: "experiment_name", label: "Experiment", group: "info", filterable: true },
  { key: "project_name", label: "Project", group: "info", filterable: true },
  { key: "cell_count", label: "Cells", group: "info" },
  // Performance columns
  { key: "avg_retention_pct", label: "Retention %", group: "performance", fmt: (v) => v != null ? formatNumber(v, 1) + "%" : "—" },
  { key: "avg_coulombic_efficiency_pct", label: "Avg CE %", group: "performance", fmt: (v) => v != null ? formatNumber(v, 2) + "%" : "—" },
  { key: "avg_fade_rate_pct_per_100_cycles", label: "Fade Rate", group: "performance", fmt: (v) => v != null ? formatNumber(v, 2) : "—" },
  { key: "avg_reversible_capacity_mAh_g", label: "Capacity (mAh/g)", group: "performance", fmt: (v) => v != null ? formatNumber(v, 1) : "—" },
  { key: "best_cycle_life_80", label: "Cycle Life (80%)", group: "performance", fmt: (v) => v != null ? Math.round(v) : "—" },
  // Processing columns
  { key: "avg_loading", label: "Loading", group: "processing", fmt: (v) => v != null ? formatNumber(v, 2) : "—" },
  { key: "avg_active_material_pct", label: "AM %", group: "processing", fmt: (v) => v != null ? formatNumber(v, 1) + "%" : "—" },
  { key: "formation_cycles", label: "Formation", group: "processing", fmt: (v) => v != null ? v : "—" },
  { key: "disc_diameter_mm", label: "Disc (mm)", group: "processing", fmt: (v) => v != null ? formatNumber(v, 1) : "—" },
  // Materials columns
  { key: "electrolyte", label: "Electrolyte", group: "materials", filterable: true },
  { key: "separator", label: "Separator", group: "materials", filterable: true },
  { key: "ontology_root_batch_name", label: "Batch", group: "materials", filterable: true },
  { key: "tracking_status", label: "Status", group: "materials", filterable: true },
];

async function loadMasterTable() {
  if (!elements.masterTableContainer) return;
  elements.masterTableContainer.innerHTML = '<div class="loading-block">Loading master table…</div>';

  try {
    const result = await api.getCohortRecords();
    const records = result.records || [];

    // Enrich records with per-cell averages where possible
    for (const r of records) {
      // Some fields may be missing from cohort records — keep what we have
      if (r.avg_loading == null && r.loading != null) r.avg_loading = r.loading;
      if (r.avg_active_material_pct == null && r.active_material_pct != null) r.avg_active_material_pct = r.active_material_pct;
    }

    state.masterTableRecords = records;
    state.masterTableLoaded = true;
    state.masterTableColumnFilters = {};
    applyMasterTableFilters();
  } catch (error) {
    elements.masterTableContainer.innerHTML = renderEmptyBlock("Master table unavailable", error.message);
  }
}

function applyMasterTableFilters() {
  let filtered = state.masterTableRecords;
  const filters = state.masterTableColumnFilters;

  for (const [col, val] of Object.entries(filters)) {
    if (!val) continue;
    filtered = filtered.filter((r) => {
      const cellVal = r[col];
      if (cellVal == null) return false;
      return String(cellVal).toLowerCase().includes(val);
    });
  }

  state.masterTableFiltered = filtered;
  renderMasterTableFilterPills();
  renderMasterTable();
}

function renderMasterTableFilterPills() {
  if (!elements.masterTableFilters) return;
  const filters = state.masterTableColumnFilters;
  const entries = Object.entries(filters).filter(([, v]) => v);

  if (!entries.length) {
    elements.masterTableFilters.innerHTML = "";
    return;
  }

  const colLabel = (key) => MASTER_TABLE_COLS.find((c) => c.key === key)?.label || key;

  elements.masterTableFilters.innerHTML = entries.map(([col, val]) =>
    `<span class="master-filter-pill" data-mt-clear-filter="${escapeHtml(col)}">
      ${escapeHtml(colLabel(col))}: <strong>${escapeHtml(val)}</strong> &times;
    </span>`
  ).join("") + `<button class="master-filter-clear-all" onclick="this.dispatchEvent(new CustomEvent('clearallfilters',{bubbles:true}))">Clear all</button>`;

  // Wire clear-all (one-shot)
  const clearBtn = elements.masterTableFilters.querySelector(".master-filter-clear-all");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      state.masterTableColumnFilters = {};
      // Clear input values in filter row
      elements.masterTableContainer.querySelectorAll("[data-mt-filter]").forEach((inp) => { inp.value = ""; });
      applyMasterTableFilters();
    }, { once: true });
  }
}

function renderMasterTable() {
  if (!elements.masterTableContainer) return;
  const records = [...state.masterTableFiltered];

  // Determine visible columns
  const visibleCols = MASTER_TABLE_COLS.filter((c) =>
    c.group === "info" || state.masterTableColumns[c.group]
  );

  if (!records.length && state.masterTableLoaded) {
    elements.masterTableContainer.innerHTML = renderEmptyBlock("No matching experiments", "Adjust your filters or load more data.");
    if (elements.masterTableCount) elements.masterTableCount.textContent = "0 experiments";
    return;
  }

  // Sort
  const col = state.masterTableSortCol;
  const asc = state.masterTableSortAsc;
  records.sort((a, b) => {
    let va = a[col], vb = b[col];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    return va < vb ? (asc ? -1 : 1) : va > vb ? (asc ? 1 : -1) : 0;
  });

  if (elements.masterTableCount) {
    const totalCount = state.masterTableRecords.length;
    const filteredCount = records.length;
    elements.masterTableCount.textContent = filteredCount === totalCount
      ? `${totalCount} experiments`
      : `${filteredCount} of ${totalCount} experiments`;
  }

  const sortIcon = (colKey) => {
    if (state.masterTableSortCol !== colKey) return "";
    return state.masterTableSortAsc ? " ▲" : " ▼";
  };

  const healthBadge = (r) => {
    const ret = r.avg_retention_pct;
    const fade = r.avg_fade_rate_pct_per_100_cycles;
    if (ret != null && ret < 80) return '<span class="health-badge health-badge--poor">Poor</span>';
    if (fade != null && fade > 5) return '<span class="health-badge health-badge--poor">High fade</span>';
    if (ret != null && ret >= 90) return '<span class="health-badge health-badge--good">Good</span>';
    if (ret != null && ret >= 80) return '<span class="health-badge health-badge--warn">Monitor</span>';
    return "";
  };

  // Preserve current filter values
  const currentFilters = state.masterTableColumnFilters;

  // Header row
  const headerCells = visibleCols.map((c) =>
    `<th class="sortable-th" data-mt-sort="${c.key}">${escapeHtml(c.label)}${sortIcon(c.key)}</th>`
  ).join("") + "<th>Health</th>";

  // Filter row
  const filterCells = visibleCols.map((c) => {
    if (c.filterable) {
      return `<th class="master-filter-cell"><input class="master-filter-input" data-mt-filter="${c.key}" type="text" placeholder="Filter…" value="${escapeHtml(currentFilters[c.key] || "")}" autocomplete="off" /></th>`;
    }
    return "<th></th>";
  }).join("") + "<th></th>";

  // Data rows
  const dataRows = records.map((r) => {
    const cells = visibleCols.map((c) => {
      const val = r[c.key];
      const formatted = c.fmt ? c.fmt(val) : (val != null ? escapeHtml(String(val)) : "—");
      return `<td>${formatted}</td>`;
    }).join("");
    return `<tr class="clickable-row" data-mt-exp-id="${r.experiment_id}" data-mt-proj-id="${r.project_id}">${cells}<td>${healthBadge(r)}</td></tr>`;
  }).join("");

  elements.masterTableContainer.innerHTML = `
    <div class="data-table-wrap master-table-scroll">
      <table class="data-table master-table">
        <thead>
          <tr>${headerCells}</tr>
          <tr class="master-filter-row">${filterCells}</tr>
        </thead>
        <tbody>${dataRows}</tbody>
      </table>
    </div>
  `;
}

function exportMasterTableCSV() {
  const records = state.masterTableFiltered;
  if (!records.length) {
    showToast("No data to export.", "error");
    return;
  }

  const visibleCols = MASTER_TABLE_COLS.filter((c) =>
    c.group === "info" || state.masterTableColumns[c.group]
  );

  const headers = visibleCols.map((c) => c.label).concat(["Health"]);
  const rows = records.map((r) => {
    const vals = visibleCols.map((c) => r[c.key] ?? "");
    const ret = r.avg_retention_pct;
    const health = ret != null ? (ret >= 90 ? "Good" : ret >= 80 ? "Monitor" : "Poor") : "";
    return [...vals, health];
  });

  downloadCSV("cellscope_master_table.csv", headers, rows);
  showToast(`Exported ${rows.length} experiments.`, "success");
}

// =====================================================================
// Analytics — Global Performance Dashboard
// =====================================================================

// Metric definitions for the analytics chart studio
const ANALYTICS_METRICS = {
  avg_retention_pct: { label: "Retention (%)", unit: "%", color: "#1e6a6a", decimals: 1 },
  avg_coulombic_efficiency_pct: { label: "CE (%)", unit: "%", color: "#3c4b63", decimals: 2 },
  avg_fade_rate_pct_per_100_cycles: { label: "Fade Rate (%/100c)", unit: "%/100c", color: "#9a3f2b", decimals: 2 },
  avg_reversible_capacity_mAh_g: { label: "Capacity (mAh/g)", unit: "mAh/g", color: "#9a7b2f", decimals: 1 },
  best_cycle_life_80: { label: "Cycle Life (80%)", unit: "cyc", color: "#6b4c8a", decimals: 0 },
  cell_count: { label: "Cell Count", unit: "", color: "#4a6741", decimals: 0 },
  avg_loading: { label: "Loading", unit: "", color: "#7a5c3a", decimals: 2 },
  avg_active_material_pct: { label: "Active Material (%)", unit: "%", color: "#3a6a7a", decimals: 1 },
};

// Plausibility bounds — values outside these ranges are physically impossible
// and arise from cycling protocol errors or data anomalies.
const PLAUSIBILITY_BOUNDS = {
  avg_retention_pct: { min: -10, max: 200 },
  avg_coulombic_efficiency_pct: { min: 30, max: 110 },
  avg_fade_rate_pct_per_100_cycles: { min: -100, max: 100 },
  avg_reversible_capacity_mAh_g: { min: 0, max: 5000 },
  best_cycle_life_80: { min: 0, max: 100000 },
  avg_loading: { min: 0, max: 100 },
  avg_active_material_pct: { min: 0, max: 100 },
};

function isPlausibleRecord(record) {
  for (const [key, bounds] of Object.entries(PLAUSIBILITY_BOUNDS)) {
    const val = record[key];
    if (val != null && (val < bounds.min || val > bounds.max)) return false;
  }
  return true;
}

// Group-by color palettes
const GROUP_PALETTE = [
  "#1e6a6a", "#9a3f2b", "#3c4b63", "#9a7b2f", "#6b4c8a",
  "#4a6741", "#7a5c3a", "#3a6a7a", "#8a4a6d", "#5a7a3a",
  "#6a3a5a", "#3a5a6a", "#7a6a3a", "#4a3a7a", "#6a7a4a",
];

const PLOTLY_BASE_LAYOUT = {
  margin: { t: 24, r: 40, b: 50, l: 60 },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  font: { family: "Avenir Next, Gill Sans, sans-serif", size: 12 },
  xaxis: { gridcolor: "rgba(31,26,21,0.06)", zeroline: false },
  yaxis: { gridcolor: "rgba(31,26,21,0.06)", automargin: true, zeroline: false },
};

const PLOTLY_CONFIG = {
  responsive: true,
  displayModeBar: "hover",
  modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
};

async function loadAnalytics() {
  if (elements.analyticsKpiBar) elements.analyticsKpiBar.innerHTML = '<div class="loading-block">Loading analytics…</div>';
  if (elements.analyticsTableContainer) elements.analyticsTableContainer.innerHTML = "";
  if (elements.analyticsStudioCharts) elements.analyticsStudioCharts.innerHTML = "";

  try {
    const result = await api.getCohortRecords();
    state.analyticsRecords = result.records || [];
    state.analyticsFilterOptions = result.filter_options || {};
    populateAnalyticsFilters();
    applyAnalyticsFilters();
  } catch (error) {
    if (elements.analyticsKpiBar) {
      elements.analyticsKpiBar.innerHTML = renderEmptyBlock("Analytics unavailable", error.message);
    }
  }
}

function populateAnalyticsFilters() {
  const opts = state.analyticsFilterOptions;

  const fillSelect = (el, items) => {
    if (!el) return;
    const current = el.value;
    el.innerHTML = `<option value="">${el.options[0]?.textContent || "All"}</option>`;
    items.forEach((item) => {
      const opt = document.createElement("option");
      if (typeof item === "object") {
        opt.value = item.id;
        opt.textContent = item.label;
      } else {
        opt.value = item;
        opt.textContent = item;
      }
      el.append(opt);
    });
    if (current) el.value = current;
  };

  fillSelect(elements.analyticsFilterProject, opts.project_options || []);
  fillSelect(elements.analyticsFilterElectrolyte, (opts.electrolytes || []).map((e) => e || "(none)"));
  fillSelect(elements.analyticsFilterBatch, opts.ontology_root_batch_names || []);
  fillSelect(elements.analyticsFilterStatus, opts.tracking_statuses || []);
}

function applyAnalyticsFilters() {
  const projVal = elements.analyticsFilterProject?.value;
  const elecVal = elements.analyticsFilterElectrolyte?.value;
  const batchVal = elements.analyticsFilterBatch?.value;
  const statusVal = elements.analyticsFilterStatus?.value;

  let filtered = state.analyticsRecords;

  if (projVal) filtered = filtered.filter((r) => String(r.project_id) === projVal);
  if (elecVal) filtered = filtered.filter((r) => (r.electrolyte || "(none)") === elecVal);
  if (batchVal) filtered = filtered.filter((r) => r.ontology_root_batch_name === batchVal);
  if (statusVal) filtered = filtered.filter((r) => r.tracking_status === statusVal);

  // Plausibility filter — remove physically impossible values
  if (state.analyticsExcludeOutliers) {
    filtered = filtered.filter(isPlausibleRecord);
  }

  // Manual exclusions
  if (state.analyticsExcludedIds.length) {
    filtered = filtered.filter((r) => !state.analyticsExcludedIds.includes(r.experiment_id));
  }

  state.analyticsFiltered = filtered;
  renderAnalyticsActiveFilters();
  renderAnalyticsKpis();
  renderAnalyticsStudio();
  renderAnalyticsStats();
  renderAnalyticsTable();
}

function clearAnalyticsFilters() {
  [elements.analyticsFilterProject, elements.analyticsFilterElectrolyte,
   elements.analyticsFilterBatch, elements.analyticsFilterStatus].forEach((el) => {
    if (el) el.value = "";
  });
  state.analyticsExcludedIds = [];
  applyAnalyticsFilters();
}

function renderAnalyticsActiveFilters() {
  if (!elements.analyticsActiveFilters) return;
  const filters = [];
  const projEl = elements.analyticsFilterProject;
  const elecEl = elements.analyticsFilterElectrolyte;
  const batchEl = elements.analyticsFilterBatch;
  const statusEl = elements.analyticsFilterStatus;

  if (projEl?.value) filters.push({ key: "project", label: projEl.options[projEl.selectedIndex]?.text || projEl.value, el: projEl });
  if (elecEl?.value) filters.push({ key: "electrolyte", label: elecEl.value, el: elecEl });
  if (batchEl?.value) filters.push({ key: "batch", label: batchEl.value, el: batchEl });
  if (statusEl?.value) filters.push({ key: "status", label: statusEl.value, el: statusEl });

  // Count how many records were removed by plausibility filter
  const outlierCount = state.analyticsExcludeOutliers
    ? state.analyticsRecords.filter((r) => !isPlausibleRecord(r)).length
    : 0;
  if (outlierCount > 0) {
    filters.push({ key: "outliers", label: `${outlierCount} outlier${outlierCount > 1 ? "s" : ""} hidden` });
  }
  if (state.analyticsExcludedIds.length) {
    filters.push({ key: "excluded", label: `${state.analyticsExcludedIds.length} manually excluded` });
  }

  if (!filters.length) {
    elements.analyticsActiveFilters.innerHTML = "";
    return;
  }

  elements.analyticsActiveFilters.innerHTML = filters.map((f) =>
    `<span class="analytics-filter-pill" data-filter-key="${f.key}">${escapeHtml(f.label)} <button type="button" aria-label="Remove filter">&times;</button></span>`
  ).join("");

  elements.analyticsActiveFilters.querySelectorAll(".analytics-filter-pill button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pill = btn.closest("[data-filter-key]");
      const key = pill.dataset.filterKey;
      if (key === "excluded") {
        state.analyticsExcludedIds = [];
        applyAnalyticsFilters();
        return;
      }
      if (key === "outliers") {
        state.analyticsExcludeOutliers = false;
        if (elements.analyticsOutlierToggle) elements.analyticsOutlierToggle.checked = false;
        applyAnalyticsFilters();
        return;
      }
      const filterMap = { project: projEl, electrolyte: elecEl, batch: batchEl, status: statusEl };
      if (filterMap[key]) filterMap[key].value = "";
      applyAnalyticsFilters();
    });
  });
}

function renderAnalyticsKpis() {
  if (!elements.analyticsKpiBar) return;
  const records = state.analyticsFiltered;

  const totalExperiments = records.length;
  const totalCells = records.reduce((s, r) => s + (r.cell_count || 0), 0);

  const retentionVals = records.map((r) => r.avg_retention_pct).filter((v) => v != null);
  const ceVals = records.map((r) => r.avg_coulombic_efficiency_pct).filter((v) => v != null);
  const fadeVals = records.map((r) => r.avg_fade_rate_pct_per_100_cycles).filter((v) => v != null);
  const cycleLifeVals = records.map((r) => r.best_cycle_life_80).filter((v) => v != null);
  const capVals = records.map((r) => r.avg_reversible_capacity_mAh_g).filter((v) => v != null);

  const avg = (arr) => arr.length ? (arr.reduce((s, v) => s + v, 0) / arr.length) : null;

  const kpis = [
    { label: "Experiments", value: totalExperiments, unit: "", cls: "" },
    { label: "Total cells", value: totalCells, unit: "", cls: "" },
    { label: "Avg retention", value: avg(retentionVals), unit: "%", decimals: 1, cls: healthClass(avg(retentionVals), 90, 80) },
    { label: "Avg CE", value: avg(ceVals), unit: "%", decimals: 2, cls: healthClass(avg(ceVals), 99, 95) },
    { label: "Avg fade rate", value: avg(fadeVals), unit: "%/100c", decimals: 2, cls: healthClassInverse(avg(fadeVals), 2, 5) },
    { label: "Avg capacity", value: avg(capVals), unit: "mAh/g", decimals: 1, cls: "" },
    { label: "Avg cycle life (80%)", value: avg(cycleLifeVals), unit: "cyc", decimals: 0, cls: "" },
  ];

  elements.analyticsKpiBar.innerHTML = kpis.map((k) => `
    <div class="analytics-kpi ${k.cls}">
      <div class="analytics-kpi-label">${escapeHtml(k.label)}</div>
      <div class="analytics-kpi-value">${k.value != null ? formatNumber(k.value, k.decimals ?? 0) : "—"}<small>${k.unit ? " " + escapeHtml(k.unit) : ""}</small></div>
    </div>
  `).join("");
}

function healthClass(val, good, warn) {
  if (val == null) return "";
  return val >= good ? "kpi-good" : val >= warn ? "kpi-warn" : "kpi-poor";
}

function healthClassInverse(val, good, warn) {
  if (val == null) return "";
  return val <= good ? "kpi-good" : val <= warn ? "kpi-warn" : "kpi-poor";
}

// --- Chart Studio rendering ---

function groupRecords(records, groupByKey) {
  if (!groupByKey) return { "All": records };
  const groups = {};
  for (const r of records) {
    const key = r[groupByKey] || "(none)";
    if (!groups[key]) groups[key] = [];
    groups[key].push(r);
  }
  return groups;
}

function renderAnalyticsStudio() {
  if (!elements.analyticsStudioCharts || !window.Plotly) return;
  elements.analyticsStudioCharts.innerHTML = "";
  const records = state.analyticsFiltered;

  if (!records.length) {
    elements.analyticsStudioCharts.innerHTML = renderEmptyBlock("No data", "Apply different filters to see charts.");
    return;
  }

  const tab = state.analyticsStudioTab;
  if (tab === "distribution") renderStudioDistribution(records);
  else if (tab === "scatter") renderStudioScatter(records);
  else if (tab === "histogram") renderStudioHistogram(records);
  else if (tab === "correlation") renderStudioCorrelation(records);
}

function renderStudioDistribution(records) {
  const container = elements.analyticsStudioCharts;
  const groupBy = state.analyticsGroupBy;
  const groups = groupRecords(records, groupBy);
  const groupNames = Object.keys(groups);
  const isGrouped = groupBy && groupNames.length > 1;

  const grid = document.createElement("div");
  grid.className = "charts-container";
  container.append(grid);

  const chartDefs = [
    { key: "avg_retention_pct", title: "Retention (%)" },
    { key: "avg_coulombic_efficiency_pct", title: "Coulombic Efficiency (%)" },
    { key: "avg_fade_rate_pct_per_100_cycles", title: "Fade Rate (%/100 cycles)" },
    { key: "avg_reversible_capacity_mAh_g", title: "Reversible Capacity (mAh/g)" },
  ];

  for (const def of chartDefs) {
    const allVals = records.map((r) => r[def.key]).filter((v) => v != null);
    if (allVals.length < 2) continue;

    const div = createChartPanel(def.title);
    grid.append(div);
    const plot = div.querySelector(".chart-target");

    const traces = [];
    if (isGrouped) {
      groupNames.forEach((gName, i) => {
        const gRecs = groups[gName];
        const vals = gRecs.map((r) => r[def.key]).filter((v) => v != null);
        const names = gRecs.filter((r) => r[def.key] != null).map((r) => r.experiment_name);
        if (!vals.length) return;
        const c = GROUP_PALETTE[i % GROUP_PALETTE.length];
        traces.push({
          y: vals, text: names, name: gName, type: "box",
          boxpoints: "all", jitter: 0.3, pointpos: -1.5,
          marker: { color: c, size: 5 }, line: { color: c },
          fillcolor: c + "20",
          hovertemplate: "%{text}<br>%{y:.2f}<extra>" + escapeHtml(gName) + "</extra>",
        });
      });
    } else {
      const vals = records.map((r) => r[def.key]).filter((v) => v != null);
      const names = records.filter((r) => r[def.key] != null).map((r) => r.experiment_name);
      const c = ANALYTICS_METRICS[def.key]?.color || "#1e6a6a";
      traces.push({
        y: vals, text: names, type: "box",
        boxpoints: "all", jitter: 0.4, pointpos: -1.5,
        marker: { color: c, size: 6 }, line: { color: c },
        fillcolor: c + "26",
        hovertemplate: "%{text}<br>%{y:.2f}<extra></extra>",
      });
    }

    Plotly.newPlot(plot, traces, {
      ...PLOTLY_BASE_LAYOUT,
      yaxis: { ...PLOTLY_BASE_LAYOUT.yaxis, title: def.title },
      showlegend: isGrouped,
      legend: { orientation: "h", y: -0.2, font: { size: 10 } },
    }, PLOTLY_CONFIG);
  }
}

function renderStudioScatter(records) {
  const container = elements.analyticsStudioCharts;
  const xKey = state.analyticsScatterX;
  const yKey = state.analyticsScatterY;
  const xMeta = ANALYTICS_METRICS[xKey] || { label: xKey };
  const yMeta = ANALYTICS_METRICS[yKey] || { label: yKey };
  const groupBy = state.analyticsGroupBy;
  const groups = groupRecords(records, groupBy);
  const groupNames = Object.keys(groups);
  const isGrouped = groupBy && groupNames.length > 1;

  const div = document.createElement("div");
  div.className = "studio-single-chart";
  container.append(div);

  const traces = [];
  if (isGrouped) {
    groupNames.forEach((gName, i) => {
      const gRecs = groups[gName];
      const pts = gRecs.filter((r) => r[xKey] != null && r[yKey] != null);
      if (!pts.length) return;
      const c = GROUP_PALETTE[i % GROUP_PALETTE.length];
      traces.push({
        x: pts.map((r) => r[xKey]), y: pts.map((r) => r[yKey]),
        text: pts.map((r) => r.experiment_name),
        customdata: pts.map((r) => [r.experiment_id, r.project_id]),
        name: gName, type: "scatter", mode: "markers",
        marker: { color: c, size: 8, opacity: 0.8, line: { width: 1, color: "#fff" } },
        hovertemplate: "%{text}<br>" + xMeta.label + ": %{x:.2f}<br>" + yMeta.label + ": %{y:.2f}<extra>" + escapeHtml(gName) + "</extra>",
      });
    });
  } else {
    const pts = records.filter((r) => r[xKey] != null && r[yKey] != null);
    if (pts.length) {
      traces.push({
        x: pts.map((r) => r[xKey]), y: pts.map((r) => r[yKey]),
        text: pts.map((r) => r.experiment_name),
        customdata: pts.map((r) => [r.experiment_id, r.project_id]),
        type: "scatter", mode: "markers",
        marker: { color: "#1e6a6a", size: 9, opacity: 0.8, line: { width: 1, color: "#fff" } },
        hovertemplate: "%{text}<br>" + xMeta.label + ": %{x:.2f}<br>" + yMeta.label + ": %{y:.2f}<extra></extra>",
      });
    }
  }

  // Trendline (linear regression over all data)
  if (state.analyticsScatterTrendline) {
    const allPts = records.filter((r) => r[xKey] != null && r[yKey] != null);
    if (allPts.length >= 3) {
      const xs = allPts.map((r) => r[xKey]);
      const ys = allPts.map((r) => r[yKey]);
      const reg = linearRegression(xs, ys);
      if (reg) {
        const xMin = Math.min(...xs);
        const xMax = Math.max(...xs);
        traces.push({
          x: [xMin, xMax], y: [reg.slope * xMin + reg.intercept, reg.slope * xMax + reg.intercept],
          mode: "lines", name: `R² = ${reg.r2.toFixed(3)}`,
          line: { color: "rgba(31,26,21,0.35)", width: 2, dash: "dot" },
          hoverinfo: "skip",
        });
      }
    }
  }

  if (!traces.length) {
    container.innerHTML = renderEmptyBlock("Insufficient data", "Not enough data points for the selected axes.");
    return;
  }

  Plotly.newPlot(div, traces, {
    ...PLOTLY_BASE_LAYOUT,
    xaxis: { ...PLOTLY_BASE_LAYOUT.xaxis, title: xMeta.label },
    yaxis: { ...PLOTLY_BASE_LAYOUT.yaxis, title: yMeta.label },
    showlegend: true,
    legend: { orientation: "h", y: -0.15, font: { size: 11 } },
    margin: { t: 24, r: 40, b: 70, l: 70 },
  }, PLOTLY_CONFIG);

  // Click to navigate
  div.on("plotly_click", (data) => {
    const pt = data.points[0];
    if (pt?.customdata) {
      const [expId, projId] = pt.customdata;
      if (projId) {
        switchView("projects");
        selectProject(projId).then(() => selectExperiment(expId));
      }
    }
  });
}

function renderStudioHistogram(records) {
  const container = elements.analyticsStudioCharts;
  const metricKey = state.analyticsHistogramMetric;
  const meta = ANALYTICS_METRICS[metricKey] || { label: metricKey };
  const groupBy = state.analyticsGroupBy;
  const groups = groupRecords(records, groupBy);
  const groupNames = Object.keys(groups);
  const isGrouped = groupBy && groupNames.length > 1;
  const binsVal = state.analyticsHistogramBins;

  const div = document.createElement("div");
  div.className = "studio-single-chart";
  container.append(div);

  const traces = [];
  if (isGrouped) {
    groupNames.forEach((gName, i) => {
      const vals = groups[gName].map((r) => r[metricKey]).filter((v) => v != null);
      if (!vals.length) return;
      const c = GROUP_PALETTE[i % GROUP_PALETTE.length];
      const trace = {
        x: vals, type: "histogram", name: gName, opacity: 0.7,
        marker: { color: c },
      };
      if (binsVal !== "auto") trace.nbinsx = Number(binsVal);
      traces.push(trace);
    });
  } else {
    const vals = records.map((r) => r[metricKey]).filter((v) => v != null);
    if (vals.length) {
      const trace = {
        x: vals, type: "histogram", name: meta.label, opacity: 0.85,
        marker: { color: ANALYTICS_METRICS[metricKey]?.color || "#1e6a6a" },
      };
      if (binsVal !== "auto") trace.nbinsx = Number(binsVal);
      traces.push(trace);
    }
  }

  if (!traces.length) {
    container.innerHTML = renderEmptyBlock("No data", "No values for the selected metric.");
    return;
  }

  Plotly.newPlot(div, traces, {
    ...PLOTLY_BASE_LAYOUT,
    xaxis: { ...PLOTLY_BASE_LAYOUT.xaxis, title: meta.label },
    yaxis: { ...PLOTLY_BASE_LAYOUT.yaxis, title: "Count" },
    barmode: isGrouped ? "overlay" : "group",
    showlegend: isGrouped,
    legend: { orientation: "h", y: -0.15, font: { size: 11 } },
    margin: { t: 24, r: 40, b: 70, l: 60 },
  }, PLOTLY_CONFIG);
}

function renderStudioCorrelation(records) {
  const container = elements.analyticsStudioCharts;
  const metricKeys = [
    "avg_retention_pct", "avg_coulombic_efficiency_pct",
    "avg_fade_rate_pct_per_100_cycles", "avg_reversible_capacity_mAh_g",
    "best_cycle_life_80",
  ];
  const labels = metricKeys.map((k) => ANALYTICS_METRICS[k]?.label || k);
  const n = metricKeys.length;

  // Build correlation matrix
  const matrix = [];
  const annotations = [];
  for (let i = 0; i < n; i++) {
    const row = [];
    for (let j = 0; j < n; j++) {
      const pairs = records.filter((r) => r[metricKeys[i]] != null && r[metricKeys[j]] != null);
      const xs = pairs.map((r) => r[metricKeys[j]]);
      const ys = pairs.map((r) => r[metricKeys[i]]);
      let corr = 0;
      if (pairs.length >= 3) {
        const reg = linearRegression(xs, ys);
        corr = reg ? (reg.r2 >= 0 ? Math.sqrt(reg.r2) : 0) : 0;
        // Determine sign from slope
        if (reg && reg.slope < 0) corr = -corr;
      }
      row.push(corr);
      annotations.push({
        x: j, y: i,
        text: pairs.length >= 3 ? corr.toFixed(2) : "—",
        showarrow: false,
        font: { size: 11, color: Math.abs(corr) > 0.5 ? "#fff" : "#1f1a15" },
      });
    }
    matrix.push(row);
  }

  const div = document.createElement("div");
  div.className = "studio-single-chart";
  container.append(div);

  Plotly.newPlot(div, [{
    z: matrix,
    x: labels,
    y: labels,
    type: "heatmap",
    colorscale: [
      [0, "#9a3f2b"], [0.25, "#e8c8a0"], [0.5, "#faf8f5"],
      [0.75, "#a0d4c8"], [1, "#1e6a6a"]
    ],
    zmin: -1, zmax: 1,
    hovertemplate: "%{y} vs %{x}<br>r = %{z:.3f}<extra></extra>",
    showscale: true,
    colorbar: { title: "r", thickness: 14, len: 0.8, tickfont: { size: 10 } },
  }], {
    ...PLOTLY_BASE_LAYOUT,
    annotations,
    xaxis: { ...PLOTLY_BASE_LAYOUT.xaxis, tickangle: -30, automargin: true },
    yaxis: { ...PLOTLY_BASE_LAYOUT.yaxis, autorange: "reversed", automargin: true },
    margin: { t: 24, r: 80, b: 100, l: 120 },
  }, PLOTLY_CONFIG);
}

// Linear regression helper
function linearRegression(xs, ys) {
  const n = xs.length;
  if (n < 2) return null;
  let sx = 0, sy = 0, sxx = 0, sxy = 0, syy = 0;
  for (let i = 0; i < n; i++) {
    sx += xs[i]; sy += ys[i];
    sxx += xs[i] * xs[i]; sxy += xs[i] * ys[i]; syy += ys[i] * ys[i];
  }
  const denom = n * sxx - sx * sx;
  if (Math.abs(denom) < 1e-12) return null;
  const slope = (n * sxy - sx * sy) / denom;
  const intercept = (sy - slope * sx) / n;
  const yMean = sy / n;
  let ssTot = 0, ssRes = 0;
  for (let i = 0; i < n; i++) {
    ssTot += (ys[i] - yMean) ** 2;
    ssRes += (ys[i] - (slope * xs[i] + intercept)) ** 2;
  }
  const r2 = ssTot > 0 ? 1 - ssRes / ssTot : 0;
  return { slope, intercept, r2 };
}

// --- Statistical Summary ---

function renderAnalyticsStats() {
  if (!elements.analyticsStatsBody) return;
  const records = state.analyticsFiltered;

  if (!records.length) {
    elements.analyticsStatsBody.innerHTML = "";
    if (elements.analyticsStatsMeta) elements.analyticsStatsMeta.textContent = "";
    return;
  }

  if (elements.analyticsStatsMeta) {
    elements.analyticsStatsMeta.textContent = `${records.length} experiments`;
  }

  const metricKeys = [
    "avg_retention_pct", "avg_coulombic_efficiency_pct",
    "avg_fade_rate_pct_per_100_cycles", "avg_reversible_capacity_mAh_g",
    "best_cycle_life_80",
  ];

  const percentile = (sorted, p) => {
    if (!sorted.length) return null;
    const idx = (p / 100) * (sorted.length - 1);
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    if (lo === hi) return sorted[lo];
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
  };

  const rows = metricKeys.map((key) => {
    const meta = ANALYTICS_METRICS[key];
    const vals = records.map((r) => r[key]).filter((v) => v != null);
    if (!vals.length) return null;

    const sorted = [...vals].sort((a, b) => a - b);
    const sum = vals.reduce((s, v) => s + v, 0);
    const mean = sum / vals.length;
    const variance = vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length;
    const stdDev = Math.sqrt(variance);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const q1 = percentile(sorted, 25);
    const median = percentile(sorted, 50);
    const q3 = percentile(sorted, 75);
    const d = meta.decimals ?? 1;

    // Sparkbar: normalize mean within min-max range
    const range = max - min;
    const sparkPct = range > 0 ? ((mean - min) / range) * 100 : 50;

    return `<tr>
      <td class="stat-metric-name">${escapeHtml(meta.label)}</td>
      <td>${vals.length}</td>
      <td>${formatNumber(mean, d)}</td>
      <td>${formatNumber(median, d)}</td>
      <td>${formatNumber(stdDev, d)}</td>
      <td>${formatNumber(min, d)}</td>
      <td>${formatNumber(q1, d)}</td>
      <td>${formatNumber(q3, d)}</td>
      <td>${formatNumber(max, d)}</td>
      <td><span class="stat-sparkbar"><span class="stat-sparkbar-fill" style="width:${sparkPct.toFixed(1)}%"></span></span></td>
    </tr>`;
  }).filter(Boolean).join("");

  elements.analyticsStatsBody.innerHTML = `
    <table class="analytics-stats-table">
      <thead>
        <tr>
          <th>Metric</th>
          <th>N</th>
          <th>Mean</th>
          <th>Median</th>
          <th>Std Dev</th>
          <th>Min</th>
          <th>Q1</th>
          <th>Q3</th>
          <th>Max</th>
          <th>Range</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// --- Enhanced table with search ---

function renderAnalyticsTable() {
  if (!elements.analyticsTableContainer) return;
  let records = [...state.analyticsFiltered];

  // Text search
  const searchTerm = (state.analyticsTableSearch || "").toLowerCase().trim();
  if (searchTerm) {
    records = records.filter((r) => {
      const haystack = [r.experiment_name, r.project_name, r.electrolyte, r.ontology_root_batch_name, r.tracking_status]
        .filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(searchTerm);
    });
  }

  if (!records.length) {
    elements.analyticsTableContainer.innerHTML = renderEmptyBlock("No data", searchTerm ? "No experiments match your search." : "No experiment records match the current filters.");
    if (elements.analyticsTableMeta) elements.analyticsTableMeta.textContent = "";
    return;
  }

  // Sort
  const col = state.analyticsSortCol;
  const asc = state.analyticsSortAsc;
  records.sort((a, b) => {
    let va = a[col], vb = b[col];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    return va < vb ? (asc ? -1 : 1) : va > vb ? (asc ? 1 : -1) : 0;
  });

  if (elements.analyticsTableMeta) {
    const totalFiltered = state.analyticsFiltered.length;
    elements.analyticsTableMeta.textContent = searchTerm
      ? `${records.length} of ${totalFiltered} experiments`
      : `${records.length} experiments`;
  }

  const sortIcon = (colName) => {
    if (state.analyticsSortCol !== colName) return "";
    return state.analyticsSortAsc ? " ▲" : " ▼";
  };

  const badgeFor = (record) => {
    const ret = record.avg_retention_pct;
    const fade = record.avg_fade_rate_pct_per_100_cycles;
    if (ret != null && ret < 80) return '<span class="health-badge health-badge--poor">Poor</span>';
    if (fade != null && fade > 5) return '<span class="health-badge health-badge--poor">High fade</span>';
    if (ret != null && ret >= 90) return '<span class="health-badge health-badge--good">Good</span>';
    if (ret != null && ret >= 80) return '<span class="health-badge health-badge--warn">Monitor</span>';
    return "";
  };

  const rows = records.map((r) => `
    <tr class="clickable-row" data-analytics-exp-id="${r.experiment_id}" data-analytics-project-id="${r.project_id}">
      <td>${escapeHtml(r.experiment_name || "—")}</td>
      <td>${escapeHtml(r.project_name || "—")}</td>
      <td>${r.cell_count ?? "—"}</td>
      <td>${escapeHtml(r.electrolyte || "—")}</td>
      <td>${escapeHtml(r.ontology_root_batch_name || "—")}</td>
      <td>${r.avg_retention_pct != null ? formatNumber(r.avg_retention_pct, 1) + "%" : "—"}</td>
      <td>${r.avg_coulombic_efficiency_pct != null ? formatNumber(r.avg_coulombic_efficiency_pct, 2) + "%" : "—"}</td>
      <td>${r.avg_fade_rate_pct_per_100_cycles != null ? formatNumber(r.avg_fade_rate_pct_per_100_cycles, 2) : "—"}</td>
      <td>${r.avg_reversible_capacity_mAh_g != null ? formatNumber(r.avg_reversible_capacity_mAh_g, 1) : "—"}</td>
      <td>${r.best_cycle_life_80 != null ? Math.round(r.best_cycle_life_80) : "—"}</td>
      <td>${badgeFor(r)}</td>
      <td><button class="exclude-btn" data-exclude-exp-id="${r.experiment_id}" type="button" title="Exclude from analytics">&times;</button></td>
    </tr>
  `).join("");

  elements.analyticsTableContainer.innerHTML = `
    <div class="data-table-wrap analytics-table-wrap">
      <table class="data-table analytics-ranking-table">
        <thead>
          <tr>
            <th class="sortable-th" data-sort-col="experiment_name">Experiment${sortIcon("experiment_name")}</th>
            <th class="sortable-th" data-sort-col="project_name">Project${sortIcon("project_name")}</th>
            <th class="sortable-th" data-sort-col="cell_count">Cells${sortIcon("cell_count")}</th>
            <th>Electrolyte</th>
            <th>Batch</th>
            <th class="sortable-th" data-sort-col="avg_retention_pct">Retention${sortIcon("avg_retention_pct")}</th>
            <th class="sortable-th" data-sort-col="avg_coulombic_efficiency_pct">CE${sortIcon("avg_coulombic_efficiency_pct")}</th>
            <th class="sortable-th" data-sort-col="avg_fade_rate_pct_per_100_cycles">Fade rate${sortIcon("avg_fade_rate_pct_per_100_cycles")}</th>
            <th class="sortable-th" data-sort-col="avg_reversible_capacity_mAh_g">Capacity${sortIcon("avg_reversible_capacity_mAh_g")}</th>
            <th class="sortable-th" data-sort-col="best_cycle_life_80">Cycle life${sortIcon("best_cycle_life_80")}</th>
            <th>Health</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function exportAnalyticsCSV() {
  const records = state.analyticsFiltered;
  if (!records.length) {
    showToast("No data to export.", "error");
    return;
  }
  const cols = [
    ["experiment_name", "Experiment"],
    ["project_name", "Project"],
    ["cell_count", "Cells"],
    ["electrolyte", "Electrolyte"],
    ["ontology_root_batch_name", "Batch"],
    ["avg_retention_pct", "Avg Retention (%)"],
    ["avg_coulombic_efficiency_pct", "Avg CE (%)"],
    ["avg_fade_rate_pct_per_100_cycles", "Fade Rate (%/100c)"],
    ["avg_reversible_capacity_mAh_g", "Avg Capacity (mAh/g)"],
    ["best_cycle_life_80", "Best Cycle Life (80%)"],
    ["tracking_status", "Status"],
  ];
  const header = cols.map(([, h]) => h);
  const rows = records.map((r) => cols.map(([k]) => {
    const v = r[k];
    return v != null ? String(v) : "";
  }));
  downloadCSV("cellscope_analytics.csv", header, rows);
}

// =====================================================================
// Cell Comparison
// =====================================================================

async function loadCellCompareProjects() {
  try {
    const projects = await api.listProjects();
    state.cellCompareProjects = projects;
    if (!elements.cellCompareProject) return;
    elements.cellCompareProject.innerHTML = '<option value="">Choose project…</option>';
    projects.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name;
      elements.cellCompareProject.append(opt);
    });
  } catch (_) {}
}

function renderCellComparePicker() {
  if (!elements.cellComparePickerList) return;
  const cells = state.cellCompareCells;
  if (!cells.length) {
    elements.cellComparePickerList.innerHTML = renderEmptyBlock("No cells", "Select an experiment with cells.");
    return;
  }
  elements.cellComparePickerList.innerHTML = cells.map((c, idx) => {
    const checked = state.cellCompareSelectedIds.includes(idx);
    const colorIdx = state.cellCompareSelectedIds.indexOf(idx);
    const hasCycling = Boolean(c.data_json);
    if (!hasCycling) return "";
    return `
      <button class="compare-run-item${checked ? " is-checked" : ""}" data-cc-cell-idx="${idx}" type="button">
        <span class="check-indicator" ${checked ? `style="background:${CHART_COLORS[colorIdx % CHART_COLORS.length]}"` : ""}></span>
        <span class="entity-list-title">${escapeHtml(c.cell_name || `Cell ${idx + 1}`)}</span>
        <span class="entity-list-meta">${c.loading != null ? formatNumber(c.loading, 2) + " mg/cm²" : ""}</span>
      </button>
    `;
  }).filter(Boolean).join("") || renderEmptyBlock("No cycling data", "None of the cells in this experiment have cycling data.");
}

function updateCellCompareButton() {
  if (!elements.cellCompareButton) return;
  const n = state.cellCompareSelectedIds.length;
  elements.cellCompareButton.textContent = `Compare selected (${n})`;
  elements.cellCompareButton.disabled = n < 2;
}

function renderCellCompareCharts() {
  if (!window.Plotly || !elements.cellCompareChartsContainer) return;
  elements.cellCompareChartsContainer.innerHTML = "";
  if (elements.cellCompareMetricsTable) elements.cellCompareMetricsTable.innerHTML = "";

  const cells = state.cellCompareCells;
  const selectedIdxs = state.cellCompareSelectedIds;

  // Parse cycling data for selected cells
  const traces = [];
  for (const idx of selectedIdxs) {
    const cell = cells[idx];
    if (!cell?.data_json) continue;
    try {
      const data = typeof cell.data_json === "string" ? JSON.parse(cell.data_json) : cell.data_json;
      const cycleKeys = Object.keys(data.Cycle || {});
      if (!cycleKeys.length) continue;
      const cyc = cycleKeys.map((k) => data.Cycle[k]);
      const dis = cycleKeys.map((k) => data["Q Dis (mAh/g)"]?.[k]);
      const chg = cycleKeys.map((k) => data["Q Chg (mAh/g)"]?.[k]);
      const eff = cycleKeys.map((k) => data["Efficiency (-)"]?.[k]);
      const fc = cell.formation_cycles || 0;
      const si = fc > 0 ? fc : 0;
      const bl = dis[si] || dis[0];
      // Last valid capacity
      let lastCap = null;
      for (let j = dis.length - 1; j >= 0; j--) {
        if (dis[j] != null && dis[j] > 0) { lastCap = dis[j]; break; }
      }
      traces.push({
        name: cell.cell_name || `Cell ${idx + 1}`,
        cycles: cyc, dischargeCap: dis, chargeCap: chg, efficiency: eff,
        formationCycles: fc, startIdx: si, baseline: bl, lastCap,
      });
    } catch (_) {}
  }

  if (!traces.length) {
    elements.cellCompareChartsContainer.innerHTML = renderEmptyBlock("No data", "Selected cells have no cycling data.");
    return;
  }

  elements.cellCompareSummaryMeta.textContent = `${traces.length} cells compared`;

  const plotlyConfig = { responsive: true, displayModeBar: "hover", modeBarButtonsToRemove: ["lasso2d", "select2d"] };
  const layout = {
    margin: { t: 10, r: 40, b: 100, l: 60 },
    legend: { orientation: "h", y: -0.35, font: { size: 11 } },
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    font: { family: "Avenir Next, Gill Sans, sans-serif" },
    xaxis: { gridcolor: "rgba(31,26,21,0.08)", automargin: true },
    yaxis: { gridcolor: "rgba(31,26,21,0.08)", automargin: true },
  };

  // 1. Discharge capacity overlay
  const capDiv = createChartPanel("Discharge Capacity");
  elements.cellCompareChartsContainer.append(capDiv);
  const capPlot = capDiv.querySelector(".chart-target");
  Plotly.newPlot(capPlot, traces.map((t, i) => ({
    x: t.cycles, y: t.dischargeCap, name: t.name, mode: "lines+markers", type: "scatter",
    line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 }, marker: { size: 4 },
    hovertemplate: "Cycle %{x}<br>%{y:.2f} mAh/g<extra>%{fullData.name}</extra>",
  })), { ...layout, xaxis: { ...layout.xaxis, title: "Cycle" }, yaxis: { ...layout.yaxis, title: "Specific Capacity (mAh/g)" } }, plotlyConfig);

  // 2. Retention overlay
  const retDiv = createChartPanel("Capacity Retention");
  elements.cellCompareChartsContainer.append(retDiv);
  const retPlot = retDiv.querySelector(".chart-target");
  Plotly.newPlot(retPlot, traces.map((t, i) => {
    const ret = t.dischargeCap.map((c) => t.baseline > 0 ? (c / t.baseline) * 100 : 0);
    return {
      x: t.cycles, y: ret, name: t.name, mode: "lines+markers", type: "scatter",
      line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 }, marker: { size: 4 },
      hovertemplate: "Cycle %{x}<br>%{y:.2f}%<extra>%{fullData.name}</extra>",
    };
  }), {
    ...layout,
    xaxis: { ...layout.xaxis, title: "Cycle" },
    yaxis: { ...layout.yaxis, title: "Retention (%)", range: [50, 105] },
    shapes: [{ type: "line", x0: 0, x1: Math.max(...traces.flatMap((t) => t.cycles)),
      y0: 80, y1: 80, line: { color: "rgba(154,63,43,0.35)", width: 1.5, dash: "dash" } }],
  }, plotlyConfig);

  // 3. CE overlay
  const ceDiv = createChartPanel("Coulombic Efficiency");
  elements.cellCompareChartsContainer.append(ceDiv);
  const cePlot = ceDiv.querySelector(".chart-target");
  Plotly.newPlot(cePlot, traces.map((t, i) => ({
    x: t.cycles, y: t.efficiency.map((e) => e != null ? e * 100 : null), name: t.name, mode: "lines+markers", type: "scatter",
    line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 }, marker: { size: 4 },
    hovertemplate: "Cycle %{x}<br>%{y:.3f}%<extra>%{fullData.name}</extra>",
  })), { ...layout, xaxis: { ...layout.xaxis, title: "Cycle" }, yaxis: { ...layout.yaxis, title: "CE (%)" } }, plotlyConfig);

  // Deferred resize — Plotly can mis-measure width when the grid layout hasn't settled yet
  requestAnimationFrame(() => {
    Plotly.Plots.resize(capPlot);
    Plotly.Plots.resize(retPlot);
    Plotly.Plots.resize(cePlot);
  });

  // 4. Metrics comparison table
  const metricRows = traces.map((t, i) => {
    const validCE = t.efficiency.slice(t.startIdx).filter((e) => e != null);
    const avgCE = validCE.length ? (validCE.reduce((s, e) => s + e, 0) / validCE.length) * 100 : null;
    const retFinal = t.baseline > 0 && t.lastCap ? (t.lastCap / t.baseline) * 100 : null;
    return `
      <tr>
        <td><span class="compare-color-swatch" style="background:${CHART_COLORS[i % CHART_COLORS.length]}"></span>${escapeHtml(t.name)}</td>
        <td>${t.dischargeCap[t.startIdx] != null ? formatNumber(t.dischargeCap[t.startIdx], 1) : "—"}</td>
        <td>${t.lastCap != null ? formatNumber(t.lastCap, 1) : "—"}</td>
        <td>${retFinal != null ? formatNumber(retFinal, 1) + "%" : "—"}</td>
        <td>${avgCE != null ? formatNumber(avgCE, 2) + "%" : "—"}</td>
        <td>${t.cycles.length}</td>
      </tr>
    `;
  }).join("");

  elements.cellCompareMetricsTable.innerHTML = `
    <div class="data-table-wrap">
      <table class="data-table">
        <thead><tr><th>Cell</th><th>Initial cap</th><th>Final cap</th><th>Retention</th><th>Avg CE</th><th>Cycles</th></tr></thead>
        <tbody>${metricRows}</tbody>
      </table>
    </div>
  `;
}

// =====================================================================
// Experiment Comparison (cross-project)
// =====================================================================

async function loadExpCompareProjects() {
  try {
    const projects = await api.listProjects();
    state.expCompareProjects = projects;
    if (!elements.expCompareProjectFilter) return;
    elements.expCompareProjectFilter.innerHTML = '<option value="">All projects</option>';
    projects.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name;
      elements.expCompareProjectFilter.append(opt);
    });

    // Load all experiments across all projects
    const allExps = [];
    for (const proj of projects) {
      const exps = await api.listExperiments(proj.id);
      exps.forEach((e) => {
        e._project_name = proj.name;
        e._project_id = proj.id;
      });
      allExps.push(...exps);
    }
    state.expCompareExperiments = allExps;
    renderExpComparePickerList();
  } catch (err) {
    if (elements.expComparePickerList) {
      elements.expComparePickerList.innerHTML = renderEmptyBlock("Failed to load", err.message);
    }
  }
}

function renderExpComparePickerList() {
  if (!elements.expComparePickerList) return;
  const projFilter = elements.expCompareProjectFilter?.value;
  let exps = state.expCompareExperiments;
  if (projFilter) {
    exps = exps.filter((e) => String(e._project_id) === projFilter);
  }

  if (!exps.length) {
    elements.expComparePickerList.innerHTML = renderEmptyBlock("No experiments", "No experiments found.");
    return;
  }

  elements.expComparePickerList.innerHTML = exps.map((e) => {
    const checked = state.expCompareSelectedIds.includes(e.id);
    const colorIdx = state.expCompareSelectedIds.indexOf(e.id);
    return `
      <button class="compare-run-item${checked ? " is-checked" : ""}" data-exp-compare-id="${e.id}" type="button">
        <span class="check-indicator" ${checked ? `style="background:${CHART_COLORS[colorIdx % CHART_COLORS.length]}"` : ""}></span>
        <div>
          <span class="entity-list-title">${escapeHtml(e.name || `Experiment #${e.id}`)}</span>
          <span class="entity-list-meta">${escapeHtml(e._project_name)} · ${e.cell_count ?? 0} cells</span>
        </div>
      </button>
    `;
  }).join("");
}

function updateExpCompareButton() {
  if (!elements.expCompareButton) return;
  const n = state.expCompareSelectedIds.length;
  elements.expCompareButton.textContent = `Compare selected (${n})`;
  elements.expCompareButton.disabled = n < 2;
}

async function loadExpCompareData() {
  const ids = state.expCompareSelectedIds;
  if (elements.expCompareSummaryMeta) {
    elements.expCompareSummaryMeta.textContent = `Loading ${ids.length} experiments…`;
  }
  if (elements.expCompareChartsContainer) {
    elements.expCompareChartsContainer.innerHTML = '<div class="compare-loading">Loading experiment data…</div>';
  }

  const results = await Promise.allSettled(ids.map((id) => api.getExperiment(id)));
  const loaded = {};
  ids.forEach((id, i) => {
    if (results[i].status === "fulfilled") loaded[id] = results[i].value;
  });
  state.expCompareLoadedData = loaded;

  if (elements.expCompareSummaryMeta) {
    elements.expCompareSummaryMeta.textContent = `${Object.keys(loaded).length} of ${ids.length} experiments loaded`;
  }

  renderExpCompareCharts();
}

function averageExperimentCycling(experiment) {
  const cells = experiment.cells || [];
  const parsedCells = [];

  for (const cell of cells) {
    if (!cell.data_json || cell.excluded) continue;
    try {
      const data = typeof cell.data_json === "string" ? JSON.parse(cell.data_json) : cell.data_json;
      const cycleKeys = Object.keys(data.Cycle || {});
      if (!cycleKeys.length) continue;
      const cyc = cycleKeys.map((k) => data.Cycle[k]);
      const dis = cycleKeys.map((k) => data["Q Dis (mAh/g)"]?.[k]);
      const chg = cycleKeys.map((k) => data["Q Chg (mAh/g)"]?.[k]);
      const eff = cycleKeys.map((k) => data["Efficiency (-)"]?.[k]);
      parsedCells.push({ cycles: cyc, dis, chg, eff, formationCycles: cell.formation_cycles || 0 });
    } catch (_) {}
  }

  if (!parsedCells.length) return null;

  // Average across cells by cycle index alignment
  const maxCycles = Math.max(...parsedCells.map((c) => c.cycles.length));
  const avgCycles = [];
  const avgDis = [];
  const avgChg = [];
  const avgEff = [];

  for (let i = 0; i < maxCycles; i++) {
    let cycleIdx = null;
    const disVals = [];
    const chgVals = [];
    const effVals = [];

    for (const pc of parsedCells) {
      if (i < pc.cycles.length) {
        if (cycleIdx == null) cycleIdx = pc.cycles[i];
        if (pc.dis[i] != null) disVals.push(pc.dis[i]);
        if (pc.chg[i] != null) chgVals.push(pc.chg[i]);
        if (pc.eff[i] != null) effVals.push(pc.eff[i]);
      }
    }

    if (cycleIdx == null) continue;
    avgCycles.push(cycleIdx);
    avgDis.push(disVals.length ? disVals.reduce((s, v) => s + v, 0) / disVals.length : null);
    avgChg.push(chgVals.length ? chgVals.reduce((s, v) => s + v, 0) / chgVals.length : null);
    avgEff.push(effVals.length ? effVals.reduce((s, v) => s + v, 0) / effVals.length : null);
  }

  const fc = parsedCells[0].formationCycles || 0;
  const si = fc > 0 ? fc : 0;
  const baseline = avgDis[si] || avgDis[0];
  let lastCap = null;
  for (let j = avgDis.length - 1; j >= 0; j--) {
    if (avgDis[j] != null && avgDis[j] > 0) { lastCap = avgDis[j]; break; }
  }

  return {
    cycles: avgCycles,
    dischargeCap: avgDis,
    chargeCap: avgChg,
    efficiency: avgEff,
    startIdx: si,
    baseline,
    lastCap,
    cellCount: parsedCells.length,
  };
}

function renderExpCompareCharts() {
  if (!window.Plotly || !elements.expCompareChartsContainer) return;
  elements.expCompareChartsContainer.innerHTML = "";
  if (elements.expCompareMetricsTable) elements.expCompareMetricsTable.innerHTML = "";

  const ids = state.expCompareSelectedIds.filter((id) => state.expCompareLoadedData[id]);
  const traces = [];

  for (const id of ids) {
    const exp = state.expCompareLoadedData[id];
    const avg = averageExperimentCycling(exp);
    if (!avg) continue;

    const projName = state.expCompareExperiments.find((e) => e.id === id)?._project_name || "";
    traces.push({
      expId: id,
      name: exp.name || `Experiment #${id}`,
      projectName: projName,
      ...avg,
    });
  }

  if (!traces.length) {
    elements.expCompareChartsContainer.innerHTML = renderEmptyBlock("No cycling data", "Selected experiments have no cycling data in their cells.");
    return;
  }

  if (elements.expCompareSummaryMeta) {
    elements.expCompareSummaryMeta.textContent = `${traces.length} experiments compared`;
  }

  const plotlyConfig = { responsive: true, displayModeBar: "hover", modeBarButtonsToRemove: ["lasso2d", "select2d"] };
  const layout = {
    margin: { t: 10, r: 40, b: 100, l: 60 },
    legend: { orientation: "h", y: -0.35, font: { size: 11 } },
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    font: { family: "Avenir Next, Gill Sans, sans-serif" },
    xaxis: { gridcolor: "rgba(31,26,21,0.08)", automargin: true },
    yaxis: { gridcolor: "rgba(31,26,21,0.08)", automargin: true },
  };

  // 1. Discharge capacity overlay
  const capDiv = createChartPanel("Discharge Capacity (avg across cells)");
  elements.expCompareChartsContainer.append(capDiv);
  const capPlot = capDiv.querySelector(".chart-target");
  Plotly.newPlot(capPlot, traces.map((t, i) => ({
    x: t.cycles, y: t.dischargeCap, name: `${t.name} (${t.projectName})`,
    mode: "lines+markers", type: "scatter",
    line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 }, marker: { size: 4 },
    hovertemplate: "Cycle %{x}<br>%{y:.2f} mAh/g<extra>%{fullData.name}</extra>",
  })), { ...layout, xaxis: { ...layout.xaxis, title: "Cycle" }, yaxis: { ...layout.yaxis, title: "Specific Capacity (mAh/g)" } }, plotlyConfig);

  // 2. Capacity retention overlay
  const retDiv = createChartPanel("Capacity Retention");
  elements.expCompareChartsContainer.append(retDiv);
  const retPlot = retDiv.querySelector(".chart-target");
  Plotly.newPlot(retPlot, traces.map((t, i) => {
    const ret = t.dischargeCap.map((c) => t.baseline > 0 ? (c / t.baseline) * 100 : 0);
    return {
      x: t.cycles, y: ret, name: `${t.name} (${t.projectName})`,
      mode: "lines+markers", type: "scatter",
      line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 }, marker: { size: 4 },
      hovertemplate: "Cycle %{x}<br>%{y:.2f}%<extra>%{fullData.name}</extra>",
    };
  }), {
    ...layout,
    xaxis: { ...layout.xaxis, title: "Cycle" },
    yaxis: { ...layout.yaxis, title: "Retention (%)", range: [50, 105] },
    shapes: [{ type: "line", x0: 0, x1: Math.max(...traces.flatMap((t) => t.cycles)),
      y0: 80, y1: 80, line: { color: "rgba(154,63,43,0.35)", width: 1.5, dash: "dash" } }],
  }, plotlyConfig);

  // 3. CE overlay
  const ceDiv = createChartPanel("Coulombic Efficiency");
  elements.expCompareChartsContainer.append(ceDiv);
  const cePlot = ceDiv.querySelector(".chart-target");
  Plotly.newPlot(cePlot, traces.map((t, i) => ({
    x: t.cycles, y: t.efficiency.map((e) => e != null ? e * 100 : null),
    name: `${t.name} (${t.projectName})`,
    mode: "lines+markers", type: "scatter",
    line: { color: CHART_COLORS[i % CHART_COLORS.length], width: 2 }, marker: { size: 4 },
    hovertemplate: "Cycle %{x}<br>%{y:.3f}%<extra>%{fullData.name}</extra>",
  })), { ...layout, xaxis: { ...layout.xaxis, title: "Cycle" }, yaxis: { ...layout.yaxis, title: "CE (%)" } }, plotlyConfig);

  // Deferred resize — Plotly can mis-measure width when the grid layout hasn't settled yet
  requestAnimationFrame(() => {
    Plotly.Plots.resize(capPlot);
    Plotly.Plots.resize(retPlot);
    Plotly.Plots.resize(cePlot);
  });

  // 4. Metrics comparison table
  const metricRows = traces.map((t, i) => {
    const validCE = t.efficiency.slice(t.startIdx).filter((e) => e != null);
    const avgCE = validCE.length ? (validCE.reduce((s, e) => s + e, 0) / validCE.length) * 100 : null;
    const retFinal = t.baseline > 0 && t.lastCap ? (t.lastCap / t.baseline) * 100 : null;
    return `
      <tr>
        <td><span class="compare-color-swatch" style="background:${CHART_COLORS[i % CHART_COLORS.length]}"></span>${escapeHtml(t.name)}</td>
        <td>${escapeHtml(t.projectName)}</td>
        <td>${t.cellCount}</td>
        <td>${t.dischargeCap[t.startIdx] != null ? formatNumber(t.dischargeCap[t.startIdx], 1) : "—"}</td>
        <td>${t.lastCap != null ? formatNumber(t.lastCap, 1) : "—"}</td>
        <td>${retFinal != null ? formatNumber(retFinal, 1) + "%" : "—"}</td>
        <td>${avgCE != null ? formatNumber(avgCE, 2) + "%" : "—"}</td>
        <td>${t.cycles.length}</td>
      </tr>
    `;
  }).join("");

  if (elements.expCompareMetricsTable) {
    elements.expCompareMetricsTable.innerHTML = `
      <div class="panel-head" style="margin-top:14px">
        <h3>Metrics comparison</h3>
      </div>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr><th>Experiment</th><th>Project</th><th>Cells</th><th>Initial cap</th><th>Final cap</th><th>Retention</th><th>Avg CE</th><th>Cycles</th></tr></thead>
          <tbody>${metricRows}</tbody>
        </table>
      </div>
    `;
  }
}

// =====================================================================
// Run Charts (Plotly)
// =====================================================================

function renderRunCharts() {
  if (!window.Plotly || !elements.runChartsContainer) return;

  const detail = state.runDetail;
  const cyclePoints = detail?.cycle_points || [];

  if (!cyclePoints.length) {
    elements.runChartsContainer.innerHTML = "";
    return;
  }

  elements.runChartsContainer.innerHTML = "";

  // Capacity chart
  const capDiv = document.createElement("div");
  capDiv.className = "chart-panel";
  capDiv.innerHTML = "<h4>Discharge Capacity</h4>";
  const capPlot = document.createElement("div");
  capDiv.append(capPlot);
  elements.runChartsContainer.append(capDiv);

  const cycles = cyclePoints.map((p) => p.cycle_index);
  const dischargeCap = cyclePoints.map((p) => p.discharge_capacity_mah);
  const chargeCap = cyclePoints.map((p) => p.charge_capacity_mah);

  Plotly.newPlot(capPlot, [
    { x: cycles, y: dischargeCap, name: "Discharge", mode: "lines+markers", type: "scatter",
      line: { color: "#9a3f2b" }, marker: { size: 4 } },
    { x: cycles, y: chargeCap, name: "Charge", mode: "lines+markers", type: "scatter",
      line: { color: "#1e6a6a" }, marker: { size: 4 } },
  ], {
    xaxis: { title: "Cycle", automargin: true },
    yaxis: { title: "Capacity (mAh)", automargin: true },
    margin: { t: 10, r: 40, b: 100, l: 60 },
    legend: { orientation: "h", y: -0.35 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  }, { responsive: true });

  // CE chart
  const ceDiv = document.createElement("div");
  ceDiv.className = "chart-panel";
  ceDiv.innerHTML = "<h4>Coulombic Efficiency</h4>";
  const cePlot = document.createElement("div");
  ceDiv.append(cePlot);
  elements.runChartsContainer.append(ceDiv);

  const ce = cyclePoints.map((p) => p.efficiency);

  Plotly.newPlot(cePlot, [
    { x: cycles, y: ce, name: "CE", mode: "lines+markers", type: "scatter",
      line: { color: "#9a7b2f" }, marker: { size: 4 } },
  ], {
    xaxis: { title: "Cycle", automargin: true },
    yaxis: { title: "Efficiency (%)", range: [95, 101], automargin: true },
    margin: { t: 10, r: 40, b: 100, l: 60 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  }, { responsive: true });
}

// ================================================================
// Experiment Designer
// ================================================================

async function loadDesignerList() {
  if (!elements.designerList) return;
  elements.designerList.innerHTML = '<div class="loading-block">Loading…</div>';
  try {
    state.designs = await api.listDesigns();
    await hydrateDesignerPickers();
    renderDesignerList();
  } catch (error) {
    elements.designerList.innerHTML = renderEmptyBlock("Experiments unavailable", error.message);
  }
}

function renderDesignerList() {
  if (!elements.designerList) return;
  const query = (elements.designerFilterInput?.value || "").toLowerCase().trim();
  const filtered = query
    ? state.designs.filter((d) => d.name.toLowerCase().includes(query) || (d.electrode_role || "").includes(query))
    : state.designs;

  if (elements.designerListCount) {
    elements.designerListCount.textContent = `${filtered.length} experiment${filtered.length !== 1 ? "s" : ""}`;
  }

  if (!filtered.length) {
    elements.designerList.innerHTML = renderEmptyBlock("No experiments", query ? "No experiments match your filter." : "Create your first experiment.");
    return;
  }

  elements.designerList.innerHTML = filtered.map((d) => {
    const isSelected = d.id === state.selectedDesignId;
    const meta = [d.status, d.electrode_role || "", d.target_project_name || ""].filter(Boolean).join(" · ");
    return `
      <button class="designer-list-item ${isSelected ? "is-selected" : ""}" data-design-id="${d.id}">
        <span class="designer-list-item-name">${escapeHtml(d.name)}</span>
        <span class="designer-list-item-meta">${escapeHtml(meta)} · ${d.num_cells} cell${d.num_cells !== 1 ? "s" : ""}</span>
      </button>
    `;
  }).join("");
}

async function hydrateDesignerPickers() {
  // Projects picker
  if (elements.designerTargetProject) {
    try {
      const projects = await api.listProjects();
      elements.designerTargetProject.innerHTML = '<option value="">-- none --</option>' +
        projects.map((p) => `<option value="${p.id}">${escapeHtml(p.name)} (${p.project_type})</option>`).join("");
    } catch { /* ignore */ }
  }

  // Fetch all materials for dropdowns (electrolyte, separator, current collector, formulation rows)
  try {
    state.ontologyMaterials = await api.listMaterials();
  } catch { state.ontologyMaterials = []; }

  // Populate electrolyte dropdown (electrolyte_salt, electrolyte_solvent, electrolyte_additive)
  const electrolyteCategories = ["electrolyte_salt", "electrolyte_solvent", "electrolyte_additive"];
  const electrolyteMats = state.ontologyMaterials.filter((m) => electrolyteCategories.includes(m.category));
  if (elements.designerElectrolyte) {
    elements.designerElectrolyte.innerHTML = '<option value="">-- select --</option>' +
      electrolyteMats.map((m) => `<option value="${escapeHtml(m.name)}">${escapeHtml(m.name)}</option>`).join("");
  }

  // Populate separator dropdown
  const separatorMats = state.ontologyMaterials.filter((m) => m.category === "separator");
  if (elements.designerSeparator) {
    elements.designerSeparator.innerHTML = '<option value="">-- select --</option>' +
      separatorMats.map((m) => `<option value="${escapeHtml(m.name)}">${escapeHtml(m.name)}</option>`).join("");
  }

  // Populate current collector dropdown
  const ccMats = state.ontologyMaterials.filter((m) => m.category === "current_collector");
  if (elements.designerCurrentCollector) {
    elements.designerCurrentCollector.innerHTML = '<option value="">-- select --</option>' +
      ccMats.map((m) => `<option value="${escapeHtml(m.name)}">${escapeHtml(m.name)}</option>`).join("");
  }

  // Protocol pickers
  try {
    const protocols = await api.listProtocolVersions();
    const optionsHtml = '<option value="">-- none --</option>' +
      protocols.map((p) => `<option value="${p.id}">${escapeHtml(p.name)} v${p.version} (${p.protocol_type})</option>`).join("");
    if (elements.designerFormationProtocol) elements.designerFormationProtocol.innerHTML = optionsHtml;
    if (elements.designerCyclingProtocol) elements.designerCyclingProtocol.innerHTML = optionsHtml;
  } catch { /* ignore */ }

  // Equipment picker
  if (elements.designerTargetEquipment) {
    try {
      const equipment = await api.listEquipmentAssets();
      const cyclers = equipment.filter((e) => e.asset_type === "cycler" || e.asset_type === "other");
      elements.designerTargetEquipment.innerHTML = '<option value="">-- none --</option>' +
        cyclers.map((e) => `<option value="${e.id}">${escapeHtml(e.name)} (${e.vendor || ""} ${e.model || ""})</option>`).join("");
    } catch { /* ignore */ }
  }

  // Operator picker
  if (elements.designerDesignedBy) {
    try {
      const operators = await api.listOperators();
      elements.designerDesignedBy.innerHTML = '<option value="">-- none --</option>' +
        operators.map((o) => `<option value="${o.id}">${escapeHtml(o.name)}${o.team ? ` (${o.team})` : ""}</option>`).join("");
    } catch { /* ignore */ }
  }
}

async function selectDesign(designId) {
  state.selectedDesignId = designId;
  renderDesignerList();

  const design = state.designs.find((d) => d.id === designId);
  if (!design) return;

  // Fetch full detail
  try {
    const full = await api.getDesign(designId);
    populateDesignerForm(full);
  } catch (error) {
    showToast(`Failed to load design: ${error.message}`, "error");
  }
}

function populateDesignerForm(design) {
  if (!elements.designerFormContent) return;
  elements.designerEmptyState.hidden = true;
  elements.designerFormContent.hidden = false;

  elements.designerName.value = design.name || "";
  elements.designerStatusBadge.textContent = design.status;
  elements.designerStatusBadge.dataset.status = design.status;
  elements.designerTimestamp.textContent = `Updated ${formatTimestamp(design.updated_at)}`;

  // Electrode
  setSelectValue(elements.designerElectrodeRole, design.electrode_role || "");
  setSelectValue(elements.designerTargetProject, design.target_project_id || "");

  // Formulation rows
  elements.designerFormulationRows.innerHTML = "";
  if (design.formulation_json && design.formulation_json.length) {
    design.formulation_json.forEach((entry) => addFormulationRow(entry));
  }
  updateFormulationTotal();

  // Electrode parameters
  setInputValue(elements.designerDiscDiameter, design.disc_diameter_mm);
  setInputValue(elements.designerLoading, design.target_loading_mg_cm2);
  setInputValue(elements.designerThickness, design.target_thickness_um);
  setInputValue(elements.designerPressedThickness, design.pressed_thickness_um);
  setInputValue(elements.designerPorosity, design.target_porosity);
  setInputValue(elements.designerSolidsContent, design.solids_content_pct);
  setInputValue(elements.designerActiveMassDensity, design.active_mass_density_g_cc);
  setInputValue(elements.designerSlurryDensity, design.slurry_density_g_ml);

  // Cell assembly
  setSelectValue(elements.designerFormFactor, design.form_factor || "");
  setSelectValue(elements.designerCurrentCollector, design.current_collector || "");
  setSelectValue(elements.designerElectrolyte, design.electrolyte || "");
  setSelectValue(elements.designerSeparator, design.separator || "");

  // Test protocol
  setSelectValue(elements.designerFormationProtocol, design.formation_protocol_id || "");
  setSelectValue(elements.designerCyclingProtocol, design.cycling_protocol_id || "");
  setInputValue(elements.designerFormationCycles, design.formation_cycles);
  setInputValue(elements.designerTemperature, design.temperature_c);
  setInputValue(elements.designerCutoffLower, design.cutoff_voltage_lower);
  setInputValue(elements.designerCutoffUpper, design.cutoff_voltage_upper);
  setInputValue(elements.designerCRateCharge, design.c_rate_charge);
  setInputValue(elements.designerCRateDischarge, design.c_rate_discharge);

  // Cell plan
  setInputValue(elements.designerNumCells, design.num_cells);
  setInputValue(elements.designerNamingPattern, design.cell_naming_pattern);
  setSelectValue(elements.designerTargetEquipment, design.target_equipment_id || "");
  setSelectValue(elements.designerDesignedBy, design.designed_by_id || "");
  setInputValue(elements.designerNotes, design.notes);

  // Realize bar state
  updateRealizeBar(design);
  updateDesignerCalculations();

  state.designerDirty = false;
}

function setInputValue(el, value) {
  if (!el) return;
  el.value = value != null ? String(value) : "";
}

function setSelectValue(el, value) {
  if (!el) return;
  el.value = String(value);
}

function collectDesignerPayload() {
  const payload = {};
  payload.name = elements.designerName?.value.trim() || "Untitled Experiment";
  payload.electrode_role = elements.designerElectrodeRole?.value || null;
  payload.target_project_id = intOrNull(elements.designerTargetProject?.value);

  // Formulation
  const rows = elements.designerFormulationRows?.querySelectorAll(".designer-formulation-row") || [];
  if (rows.length) {
    payload.formulation_json = [...rows].map((row) => ({
      material_name: row.querySelector("[data-field='material_name']")?.value.trim() || "Unknown",
      category: row.querySelector("[data-field='category']")?.value || null,
      dry_mass_fraction_pct: parseFloat(row.querySelector("[data-field='dry_mass_fraction_pct']")?.value) || 0,
    }));
  } else {
    payload.formulation_json = null;
  }

  // Electrode parameters
  payload.disc_diameter_mm = floatOrNull(elements.designerDiscDiameter?.value);
  payload.target_loading_mg_cm2 = floatOrNull(elements.designerLoading?.value);
  payload.target_thickness_um = floatOrNull(elements.designerThickness?.value);
  payload.pressed_thickness_um = floatOrNull(elements.designerPressedThickness?.value);
  payload.target_porosity = floatOrNull(elements.designerPorosity?.value);
  payload.solids_content_pct = floatOrNull(elements.designerSolidsContent?.value);
  payload.active_mass_density_g_cc = floatOrNull(elements.designerActiveMassDensity?.value);
  payload.slurry_density_g_ml = floatOrNull(elements.designerSlurryDensity?.value);

  // Cell assembly
  payload.form_factor = elements.designerFormFactor?.value || null;
  payload.electrolyte = elements.designerElectrolyte?.value || null;
  payload.separator = elements.designerSeparator?.value || null;
  payload.current_collector = elements.designerCurrentCollector?.value || null;

  // Test protocol
  payload.formation_protocol_id = intOrNull(elements.designerFormationProtocol?.value);
  payload.cycling_protocol_id = intOrNull(elements.designerCyclingProtocol?.value);
  payload.formation_cycles = intOrNull(elements.designerFormationCycles?.value);
  payload.temperature_c = floatOrNull(elements.designerTemperature?.value);
  payload.cutoff_voltage_lower = floatOrNull(elements.designerCutoffLower?.value);
  payload.cutoff_voltage_upper = floatOrNull(elements.designerCutoffUpper?.value);
  payload.c_rate_charge = floatOrNull(elements.designerCRateCharge?.value);
  payload.c_rate_discharge = floatOrNull(elements.designerCRateDischarge?.value);

  // Cell plan
  payload.num_cells = intOrNull(elements.designerNumCells?.value) || 3;
  payload.cell_naming_pattern = elements.designerNamingPattern?.value.trim() || null;
  payload.target_equipment_id = intOrNull(elements.designerTargetEquipment?.value);
  payload.designed_by_id = intOrNull(elements.designerDesignedBy?.value);
  payload.notes = elements.designerNotes?.value.trim() || null;

  return payload;
}

function floatOrNull(val) {
  if (val == null || val === "") return null;
  const n = parseFloat(val);
  return isNaN(n) ? null : n;
}

function intOrNull(val) {
  if (val == null || val === "") return null;
  const n = parseInt(val, 10);
  return isNaN(n) ? null : n;
}

async function createNewDesign() {
  const defaultFormulation = [
    { material_name: "", category: "cathode_active", dry_mass_fraction_pct: 90 },
    { material_name: "", category: "conductive_additive", dry_mass_fraction_pct: 5 },
    { material_name: "", category: "binder", dry_mass_fraction_pct: 5 },
  ];
  const payload = { name: "New Experiment", formulation_json: defaultFormulation };
  try {
    const created = await api.createDesign(payload);
    state.designs.unshift({
      id: created.id,
      name: created.name,
      status: created.status,
      electrode_role: created.electrode_role,
      target_project_id: created.target_project_id,
      target_project_name: created.target_project_name,
      num_cells: created.num_cells,
      created_at: created.created_at,
      updated_at: created.updated_at,
    });
    renderDesignerList();
    await selectDesign(created.id);
    elements.designerName?.focus();
    elements.designerName?.select();
    showToast("Experiment created.", "success");
  } catch (error) {
    showToast(`Create failed: ${error.message}`, "error");
  }
}

async function saveCurrentDesign() {
  if (!state.selectedDesignId) return;
  const payload = collectDesignerPayload();
  try {
    const updated = await api.updateDesign(state.selectedDesignId, payload);
    // Update list entry
    const idx = state.designs.findIndex((d) => d.id === state.selectedDesignId);
    if (idx >= 0) {
      state.designs[idx] = {
        ...state.designs[idx],
        name: updated.name,
        status: updated.status,
        electrode_role: updated.electrode_role,
        target_project_id: updated.target_project_id,
        target_project_name: updated.target_project_name,
        num_cells: updated.num_cells,
        updated_at: updated.updated_at,
      };
    }
    renderDesignerList();
    elements.designerStatusBadge.textContent = updated.status;
    elements.designerStatusBadge.dataset.status = updated.status;
    elements.designerTimestamp.textContent = `Updated ${formatTimestamp(updated.updated_at)}`;
    state.designerDirty = false;
    showToast("Experiment saved.", "success");
  } catch (error) {
    showToast(`Save failed: ${error.message}`, "error");
  }
}

async function duplicateCurrentDesign() {
  if (!state.selectedDesignId) return;
  try {
    const copy = await api.duplicateDesign(state.selectedDesignId);
    await loadDesignerList();
    await selectDesign(copy.id);
    showToast("Experiment duplicated.", "success");
  } catch (error) {
    showToast(`Duplicate failed: ${error.message}`, "error");
  }
}

async function deleteCurrentDesign() {
  if (!state.selectedDesignId) return;
  const design = state.designs.find((d) => d.id === state.selectedDesignId);
  if (!window.confirm(`Delete "${design?.name || ""}"? This cannot be undone.`)) return;
  try {
    await api.deleteDesign(state.selectedDesignId);
    state.selectedDesignId = null;
    elements.designerEmptyState.hidden = false;
    elements.designerFormContent.hidden = true;
    await loadDesignerList();
    showToast("Experiment deleted.", "success");
  } catch (error) {
    showToast(`Delete failed: ${error.message}`, "error");
  }
}

async function markDesignReady() {
  if (!state.selectedDesignId) return;
  try {
    const updated = await api.updateDesign(state.selectedDesignId, { status: "ready" });
    const idx = state.designs.findIndex((d) => d.id === state.selectedDesignId);
    if (idx >= 0) state.designs[idx].status = "ready";
    renderDesignerList();
    elements.designerStatusBadge.textContent = "ready";
    elements.designerStatusBadge.dataset.status = "ready";
    updateRealizeBar(updated);
    showToast("Marked as ready.", "success");
  } catch (error) {
    showToast(`Status update failed: ${error.message}`, "error");
  }
}

async function realizeCurrentDesign() {
  if (!state.selectedDesignId) return;
  let projectId = intOrNull(elements.designerTargetProject?.value);
  if (!projectId) {
    showToast("Select a target project before realizing.", "warn");
    elements.designerTargetProject?.focus();
    return;
  }
  const designName = elements.designerName?.value.trim() || "";
  if (!window.confirm(`Realize "${designName}" into the selected project? This will create a real experiment with ${elements.designerNumCells?.value || 3} cells.`)) return;

  try {
    // Save first to persist any unsaved changes
    await saveCurrentDesign();
    const result = await api.realizeDesign(state.selectedDesignId, {
      project_id: projectId,
      experiment_name: designName || null,
    });
    const idx = state.designs.findIndex((d) => d.id === state.selectedDesignId);
    if (idx >= 0) state.designs[idx].status = "realized";
    renderDesignerList();
    populateDesignerForm(result);
    showToast("Realized! Experiment and cells created.", "success");
  } catch (error) {
    showToast(`Realize failed: ${error.message}`, "error");
  }
}

function updateRealizeBar(design) {
  if (!elements.designerRealizeBar) return;
  const isRealized = design.status === "realized";
  const isReady = design.status === "ready";

  if (elements.designerMarkReady) {
    elements.designerMarkReady.hidden = isRealized || isReady;
  }
  if (elements.designerRealizeButton) {
    elements.designerRealizeButton.hidden = isRealized;
  }
  if (elements.designerRealizeStatus) {
    if (isRealized && design.realized_experiment_id) {
      elements.designerRealizeStatus.innerHTML = `Realized as experiment #${design.realized_experiment_id}`;
    } else if (isReady) {
      elements.designerRealizeStatus.textContent = "Ready to realize — select a target project and click Realize.";
    } else {
      elements.designerRealizeStatus.textContent = "Save your design, then mark it ready when complete.";
    }
  }
}

// --- Formulation rows ---

function addFormulationRow(entry = null) {
  if (!elements.designerFormulationRows) return;
  const row = document.createElement("div");
  row.className = "designer-formulation-row";

  const materialName = entry?.material_name || "";
  const category = entry?.category || "";
  const pct = entry?.dry_mass_fraction_pct != null ? entry.dry_mass_fraction_pct : "";

  const categoryOptions = [
    "", "cathode_active", "anode_active", "binder", "conductive_additive",
    "electrolyte_salt", "electrolyte_solvent", "separator", "current_collector", "other",
  ];
  const categoryLabels = [
    "-- category --", "Cathode active", "Anode active", "Binder", "Conductive additive",
    "Electrolyte salt", "Electrolyte solvent", "Separator", "Current collector", "Other",
  ];

  row.innerHTML = `
    <select data-field="material_name" style="flex:2">
      <option value="">-- select material --</option>
    </select>
    <select data-field="category" style="flex:1">
      ${categoryOptions.map((opt, i) => `<option value="${opt}"${opt === category ? " selected" : ""}>${categoryLabels[i]}</option>`).join("")}
    </select>
    <input type="number" data-field="dry_mass_fraction_pct" value="${pct}" placeholder="%" step="0.1" min="0" max="100" style="flex:0.7" />
    <button type="button" class="formulation-remove" title="Remove">&times;</button>
  `;

  const categorySelect = row.querySelector("[data-field='category']");
  const materialSelect = row.querySelector("[data-field='material_name']");

  // Populate material dropdown filtered by selected category
  function refreshMaterialOptions() {
    const cat = categorySelect.value;
    const filtered = cat
      ? state.ontologyMaterials.filter((m) => m.category === cat)
      : state.ontologyMaterials;
    const currentVal = materialSelect.value;
    materialSelect.innerHTML = '<option value="">-- select material --</option>' +
      filtered.map((m) => `<option value="${escapeHtml(m.name)}">${escapeHtml(m.name)}</option>`).join("");
    // Restore selection if still available
    if (currentVal) materialSelect.value = currentVal;
    updateDesignerCalculations();
  }

  categorySelect.addEventListener("change", refreshMaterialOptions);
  materialSelect.addEventListener("change", () => updateDesignerCalculations());

  // Initial population
  refreshMaterialOptions();
  if (materialName) materialSelect.value = materialName;

  row.querySelector(".formulation-remove").addEventListener("click", () => {
    row.remove();
    updateFormulationTotal();
    updateDesignerCalculations();
  });

  row.querySelector("[data-field='dry_mass_fraction_pct']").addEventListener("input", () => {
    updateFormulationTotal();
    updateDesignerCalculations();
  });

  elements.designerFormulationRows.appendChild(row);
  updateFormulationTotal();
}

function updateFormulationTotal() {
  if (!elements.designerFormulationTotal) return;
  const rows = elements.designerFormulationRows?.querySelectorAll(".designer-formulation-row") || [];
  let total = 0;
  rows.forEach((row) => {
    const val = parseFloat(row.querySelector("[data-field='dry_mass_fraction_pct']")?.value);
    if (!isNaN(val)) total += val;
  });
  const rounded = Math.round(total * 100) / 100;
  elements.designerFormulationTotal.textContent = `Total: ${rounded}%`;
  elements.designerFormulationTotal.classList.toggle("is-valid", Math.abs(rounded - 100) < 0.1);
  elements.designerFormulationTotal.classList.toggle("is-invalid", rounded > 0 && Math.abs(rounded - 100) >= 0.1);
}

// --- Live calculations ---

function updateDesignerCalculations() {
  const diameter = floatOrNull(elements.designerDiscDiameter?.value);
  const loading = floatOrNull(elements.designerLoading?.value);
  const thickness = floatOrNull(elements.designerThickness?.value);
  const pressedThickness = floatOrNull(elements.designerPressedThickness?.value);
  const activeMassDensity = floatOrNull(elements.designerActiveMassDensity?.value);

  // Get active material % from formulation
  let activePct = null;
  const rows = elements.designerFormulationRows?.querySelectorAll(".designer-formulation-row") || [];
  for (const row of rows) {
    const cat = row.querySelector("[data-field='category']")?.value || "";
    if (cat.includes("active")) {
      const val = parseFloat(row.querySelector("[data-field='dry_mass_fraction_pct']")?.value);
      if (!isNaN(val)) { activePct = val; break; }
    }
  }

  // Disc area (cm²) = π × (d_mm / 20)²
  const discArea = diameter ? Math.PI * Math.pow(diameter / 20, 2) : null;
  setCalcValue("calcDiscArea", discArea, 4);

  // Active material mass (mg) = loading × area
  const activeMass = (loading && discArea) ? loading * discArea : null;
  setCalcValue("calcActiveMass", activeMass, 2);

  // Disc mass (mg) = activeMass / (activePct / 100)
  const discMass = (activeMass && activePct) ? activeMass / (activePct / 100) : null;
  setCalcValue("calcDiscMass", discMass, 2);

  // Thickness reduction (%) = (thickness - pressed) / thickness × 100
  const thicknessReduction = (thickness && pressedThickness && thickness > 0)
    ? ((thickness - pressedThickness) / thickness) * 100 : null;
  setCalcValue("calcThicknessReduction", thicknessReduction, 1);

  // Electrode density (g/mL) — from active mass density and porosity
  // If we have disc mass and pressed thickness and disc area:
  // electrode_density = disc_mass_mg / 1000 / (pressed_thickness_um / 10000 * disc_area)
  let electrodeDensity = null;
  const effectiveThickness = pressedThickness || thickness;
  if (discMass && effectiveThickness && discArea) {
    // disc_mass in mg → g: /1000; thickness in μm → cm: /10000; area in cm²
    electrodeDensity = (discMass / 1000) / ((effectiveThickness / 10000) * discArea);
  }
  setCalcValue("calcElectrodeDensity", electrodeDensity, 3);

  // Theoretical capacity (mAh) — using NMC811 ~200 mAh/g specific capacity as reference
  // capacity = loading_mg/cm² × area_cm² × specific_capacity_mAh/g / 1000 (mg→g)
  const specificCapacity = getSpecificCapacity();
  const theoCapacity = (loading && discArea && specificCapacity)
    ? (loading * discArea * specificCapacity) / 1000 : null;
  setCalcValue("calcTheoCapacity", theoCapacity, 3);
}

function getSpecificCapacity() {
  // Infer specific capacity from formulation material name
  const rows = elements.designerFormulationRows?.querySelectorAll(".designer-formulation-row") || [];
  for (const row of rows) {
    const cat = row.querySelector("[data-field='category']")?.value || "";
    if (!cat.includes("active")) continue;
    const name = (row.querySelector("[data-field='material_name']")?.value || "").toLowerCase();
    if (name.includes("nmc811") || name.includes("nmc 811")) return 200;
    if (name.includes("nmc622") || name.includes("nmc 622")) return 180;
    if (name.includes("nmc532") || name.includes("nmc 532")) return 165;
    if (name.includes("nmc111") || name.includes("nmc 111")) return 160;
    if (name.includes("nca")) return 200;
    if (name.includes("lco")) return 145;
    if (name.includes("lfp") || name.includes("lifepo4")) return 170;
    if (name.includes("lmo")) return 120;
    if (name.includes("graphite")) return 372;
    if (name.includes("silicon") || name.includes("si")) return 1000;
    if (name.includes("lto")) return 175;
    return 200; // default for unknown active materials
  }
  return null;
}

function setCalcValue(elementId, value, decimals) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = value != null ? value.toFixed(decimals) : "--";
}

function renderEmptyBlock(title, body) {
  return `
    <article class="empty-block">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(body)}</p>
    </article>
  `;
}

function showToast(message, tone = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${tone}`;
  toast.textContent = message;
  elements.toastRegion.append(toast);
  window.setTimeout(() => {
    toast.classList.add("is-leaving");
    window.setTimeout(() => toast.remove(), 240);
  }, 3200);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function emptyToNull(value) {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function compactPath(filePath) {
  if (!filePath) {
    return "—";
  }
  const parts = String(filePath).split("/");
  return parts.slice(-3).join("/");
}

function formatTimestamp(value) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function formatPercent(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return `${value.toFixed(1)}%`;
}

function formatNumber(value, digits = 1) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(digits);
}

function formatMetricValue(valueNumeric, valueJson, unit) {
  if (typeof valueNumeric === "number" && !Number.isNaN(valueNumeric)) {
    return `${valueNumeric.toFixed(3)}${unit ? ` ${unit}` : ""}`;
  }
  if (valueJson && typeof valueJson === "object") {
    return JSON.stringify(valueJson);
  }
  return "No value";
}

function downloadCSV(filename, headers, rows) {
  const escapeCsvCell = (val) => {
    const str = val == null ? "" : String(val);
    return str.includes(",") || str.includes('"') || str.includes("\n")
      ? `"${str.replace(/"/g, '""')}"`
      : str;
  };
  const lines = [headers.map(escapeCsvCell).join(",")];
  for (const row of rows) {
    lines.push(row.map(escapeCsvCell).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function withButtonBusy(button, action) {
  if (!button) {
    return action();
  }
  const previous = button.disabled;
  button.disabled = true;
  try {
    return await action();
  } catch (error) {
    showToast(error.message, "error");
    throw error;
  } finally {
    button.disabled = previous;
  }
}

async function withFormBusy(form, action) {
  if (!form) {
    return action();
  }
  const submitButtons = [...form.querySelectorAll("button, input, select, textarea")];
  submitButtons.forEach((element) => {
    element.disabled = true;
  });
  try {
    return await action();
  } catch (error) {
    showToast(error.message, "error");
    throw error;
  } finally {
    submitButtons.forEach((element) => {
      element.disabled = false;
    });
  }
}
