import http from 'node:http';

import { getConfig } from './config.js';
import { initDatabase } from './db/connection.js';
import { createStore } from './db/store.js';
import { HttpError } from './lib/errors.js';
import { parseJsonText, readJsonBody, toSafeInt, writeJson, writeNoContent } from './lib/http.js';
import { serializeCell, serializeDataSource, serializeExperiment, serializeProject } from './lib/serializers.js';
import {
  getProjectType,
  normalizeFormulation,
  normalizeGroupNames,
  optionalBoolean,
  optionalInteger,
  optionalNumber,
  optionalString,
  paginationFromQuery,
  requiredString,
} from './lib/validation.js';

function parseFlag(value) {
  if (value === null || value === undefined) {
    return false;
  }

  const normalized = String(value).trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes';
}

function pathToRegex(pathTemplate) {
  const keys = [];
  const escaped = pathTemplate
    .split('/')
    .filter(Boolean)
    .map((segment) => {
      if (segment.startsWith(':')) {
        keys.push(segment.slice(1));
        return '([^/]+)';
      }
      return segment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    });

  return {
    keys,
    regex: new RegExp(`^/${escaped.join('/')}/?$`),
  };
}

function createRouter(routes) {
  const compiled = routes.map((route) => ({ ...route, ...pathToRegex(route.path) }));

  return {
    match(method, pathname) {
      for (const route of compiled) {
        if (route.method !== method) {
          continue;
        }
        const match = pathname.match(route.regex);
        if (!match) {
          continue;
        }

        const params = {};
        route.keys.forEach((key, index) => {
          params[key] = decodeURIComponent(match[index + 1]);
        });

        return { route, params };
      }

      return null;
    },
  };
}

function jsonOrString(value) {
  if (value === undefined || value === null) {
    return null;
  }

  if (typeof value === 'string') {
    return value;
  }

  return JSON.stringify(value);
}

function normalizeDataSources(body) {
  const normalized = [];

  if (Array.isArray(body.data_sources)) {
    for (const source of body.data_sources) {
      if (!source || typeof source !== 'object') {
        continue;
      }

      const mapped = {
        source_type: optionalString(source.source_type, 'data_sources.source_type', 100) ?? 'parquet',
        path: optionalString(source.path, 'data_sources.path', 2000),
        payload_json: source.payload_json ?? null,
        metadata: source.metadata ?? source.metadata_json ?? null,
      };

      if (mapped.path !== null || mapped.payload_json !== null) {
        normalized.push(mapped);
      }
    }
  }

  const parquetPath = optionalString(body.parquet_path, 'parquet_path', 2000);
  if (parquetPath) {
    normalized.push({ source_type: 'parquet', path: parquetPath, payload_json: null, metadata: null });
  }

  if (body.data_json !== undefined && body.data_json !== null) {
    normalized.push({
      source_type: 'legacy_json',
      path: null,
      payload_json: body.data_json,
      metadata: null,
    });
  }

  return normalized;
}

function serializePreference(row) {
  return {
    key: row.preference_key,
    value: parseJsonText(row.preference_value, row.preference_value),
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function buildRoutes(config, store) {
  return createRouter([
    {
      method: 'GET',
      path: '/api/health',
      async handler(_ctx) {
        return {
          status: 200,
          body: {
            status: 'ok',
            app: config.appName,
            version: config.version,
          },
        };
      },
    },

    {
      method: 'GET',
      path: '/api/projects',
      async handler(ctx) {
        const { limit, cursor } = paginationFromQuery(ctx.url.searchParams);
        const page = store.listProjects({ limit, cursor });

        return {
          status: 200,
          body: {
            data: page.items.map(serializeProject),
            page: {
              limit,
              next_cursor: page.nextCursor,
            },
          },
        };
      },
    },

    {
      method: 'POST',
      path: '/api/projects',
      async handler(ctx) {
        const body = await readJsonBody(ctx.req);
        const project = store.createProject({
          user_id: optionalString(body.user_id, 'user_id', 255) ?? 'admin',
          name: requiredString(body.name, 'name', 255),
          description: optionalString(body.description, 'description', 2000),
          project_type: getProjectType(body.project_type) ?? 'Full Cell',
        });

        return {
          status: 201,
          body: {
            data: serializeProject(project),
          },
        };
      },
    },

    {
      method: 'GET',
      path: '/api/projects/:projectId',
      async handler(ctx) {
        const projectId = toSafeInt(ctx.params.projectId, 'projectId');
        const project = store.getProject(projectId);
        if (!project) {
          throw new HttpError(404, 'Project not found');
        }

        const includePreferences = parseFlag(ctx.url.searchParams.get('include_preferences'));
        return {
          status: 200,
          body: {
            data: serializeProject(project),
            preferences: includePreferences
              ? store.listProjectPreferences(projectId).map(serializePreference)
              : undefined,
          },
        };
      },
    },

    {
      method: 'PATCH',
      path: '/api/projects/:projectId',
      async handler(ctx) {
        const projectId = toSafeInt(ctx.params.projectId, 'projectId');
        const body = await readJsonBody(ctx.req);

        const updates = {};
        if (body.name !== undefined) {
          updates.name = requiredString(body.name, 'name', 255);
        }
        if (body.description !== undefined) {
          updates.description = optionalString(body.description, 'description', 2000);
        }
        if (body.project_type !== undefined) {
          updates.project_type = getProjectType(body.project_type, { required: true });
        }

        const project = store.updateProject(projectId, updates);
        if (!project) {
          throw new HttpError(404, 'Project not found');
        }

        return {
          status: 200,
          body: {
            data: serializeProject(project),
          },
        };
      },
    },

    {
      method: 'DELETE',
      path: '/api/projects/:projectId',
      async handler(ctx) {
        const projectId = toSafeInt(ctx.params.projectId, 'projectId');
        const deleted = store.deleteProject(projectId);
        if (!deleted) {
          throw new HttpError(404, 'Project not found');
        }

        return { status: 204, body: null };
      },
    },

    {
      method: 'GET',
      path: '/api/projects/:projectId/experiments',
      async handler(ctx) {
        const projectId = toSafeInt(ctx.params.projectId, 'projectId');
        const project = store.getProject(projectId);
        if (!project) {
          throw new HttpError(404, 'Project not found');
        }

        const { limit, cursor } = paginationFromQuery(ctx.url.searchParams);
        const page = store.listExperiments(projectId, { limit, cursor });
        return {
          status: 200,
          body: {
            data: page.items.map(serializeExperiment),
            page: {
              limit,
              next_cursor: page.nextCursor,
            },
          },
        };
      },
    },

    {
      method: 'POST',
      path: '/api/projects/:projectId/experiments',
      async handler(ctx) {
        const projectId = toSafeInt(ctx.params.projectId, 'projectId');
        const project = store.getProject(projectId);
        if (!project) {
          throw new HttpError(404, 'Project not found');
        }

        const body = await readJsonBody(ctx.req);
        const experiment = store.createExperiment(projectId, {
          name: requiredString(body.name, 'name', 255),
          experiment_date: optionalString(body.experiment_date, 'experiment_date', 50),
          disc_diameter_mm: optionalNumber(body.disc_diameter_mm, 'disc_diameter_mm'),
          solids_content: optionalNumber(body.solids_content, 'solids_content'),
          pressed_thickness: optionalNumber(body.pressed_thickness, 'pressed_thickness'),
          notes: optionalString(body.notes, 'notes', 5000),
          group_names: normalizeGroupNames(body.group_names),
          metadata: body.metadata ?? null,
        });

        return {
          status: 201,
          body: {
            data: serializeExperiment(experiment),
          },
        };
      },
    },

    {
      method: 'GET',
      path: '/api/experiments/:experimentId',
      async handler(ctx) {
        const experimentId = toSafeInt(ctx.params.experimentId, 'experimentId');
        const experiment = store.getExperiment(experimentId);
        if (!experiment) {
          throw new HttpError(404, 'Experiment not found');
        }

        const includeCells = parseFlag(ctx.url.searchParams.get('include_cells'));
        const responseBody = {
          data: serializeExperiment(experiment),
        };

        if (includeCells) {
          const cellLimit = Number(ctx.url.searchParams.get('cell_limit') ?? 100);
          const safeCellLimit = Number.isInteger(cellLimit) && cellLimit > 0
            ? Math.min(cellLimit, 500)
            : 100;

          const cellsPage = store.listCells(experimentId, { limit: safeCellLimit, cursor: null });
          responseBody.cells = cellsPage.items.map(serializeCell);
          responseBody.cells_page = {
            limit: safeCellLimit,
            next_cursor: cellsPage.nextCursor,
          };
        }

        return {
          status: 200,
          body: responseBody,
        };
      },
    },

    {
      method: 'PATCH',
      path: '/api/experiments/:experimentId',
      async handler(ctx) {
        const experimentId = toSafeInt(ctx.params.experimentId, 'experimentId');
        const body = await readJsonBody(ctx.req);

        const updates = {};
        if (body.name !== undefined) {
          updates.name = requiredString(body.name, 'name', 255);
        }
        if (body.experiment_date !== undefined) {
          updates.experiment_date = optionalString(body.experiment_date, 'experiment_date', 50);
        }
        if (body.disc_diameter_mm !== undefined) {
          updates.disc_diameter_mm = optionalNumber(body.disc_diameter_mm, 'disc_diameter_mm');
        }
        if (body.solids_content !== undefined) {
          updates.solids_content = optionalNumber(body.solids_content, 'solids_content');
        }
        if (body.pressed_thickness !== undefined) {
          updates.pressed_thickness = optionalNumber(body.pressed_thickness, 'pressed_thickness');
        }
        if (body.notes !== undefined) {
          updates.notes = optionalString(body.notes, 'notes', 5000);
        }
        if (body.group_names !== undefined) {
          updates.group_names = normalizeGroupNames(body.group_names);
        }
        if (body.metadata !== undefined) {
          updates.metadata = body.metadata;
        }

        const experiment = store.updateExperiment(experimentId, updates);
        if (!experiment) {
          throw new HttpError(404, 'Experiment not found');
        }

        return {
          status: 200,
          body: {
            data: serializeExperiment(experiment),
          },
        };
      },
    },

    {
      method: 'DELETE',
      path: '/api/experiments/:experimentId',
      async handler(ctx) {
        const experimentId = toSafeInt(ctx.params.experimentId, 'experimentId');
        const deleted = store.deleteExperiment(experimentId);
        if (!deleted) {
          throw new HttpError(404, 'Experiment not found');
        }

        return { status: 204, body: null };
      },
    },

    {
      method: 'GET',
      path: '/api/experiments/:experimentId/cells',
      async handler(ctx) {
        const experimentId = toSafeInt(ctx.params.experimentId, 'experimentId');
        const experiment = store.getExperiment(experimentId);
        if (!experiment) {
          throw new HttpError(404, 'Experiment not found');
        }

        const { limit, cursor } = paginationFromQuery(ctx.url.searchParams);
        const page = store.listCells(experimentId, { limit, cursor });

        return {
          status: 200,
          body: {
            data: page.items.map(serializeCell),
            page: {
              limit,
              next_cursor: page.nextCursor,
            },
          },
        };
      },
    },

    {
      method: 'POST',
      path: '/api/experiments/:experimentId/cells',
      async handler(ctx) {
        const experimentId = toSafeInt(ctx.params.experimentId, 'experimentId');
        const experiment = store.getExperiment(experimentId);
        if (!experiment) {
          throw new HttpError(404, 'Experiment not found');
        }

        const body = await readJsonBody(ctx.req);
        const cell = store.createCell(experimentId, {
          cell_name: requiredString(body.cell_name, 'cell_name', 255),
          file_name: optionalString(body.file_name, 'file_name', 255),
          loading: optionalNumber(body.loading, 'loading'),
          active_material_pct: optionalNumber(body.active_material_pct, 'active_material_pct'),
          formation_cycles: optionalInteger(body.formation_cycles, 'formation_cycles') ?? 4,
          test_number: optionalString(body.test_number, 'test_number', 100),
          electrolyte: optionalString(body.electrolyte, 'electrolyte', 255),
          substrate: optionalString(body.substrate, 'substrate', 100),
          separator: optionalString(body.separator, 'separator', 100),
          formulation: normalizeFormulation(body.formulation),
          group_assignment: optionalString(body.group_assignment, 'group_assignment', 100),
          excluded: optionalBoolean(body.excluded) ?? false,
          porosity: optionalNumber(body.porosity, 'porosity'),
          cutoff_voltage_lower: optionalNumber(body.cutoff_voltage_lower, 'cutoff_voltage_lower'),
          cutoff_voltage_upper: optionalNumber(body.cutoff_voltage_upper, 'cutoff_voltage_upper'),
          anode_mass: optionalNumber(body.anode_mass, 'anode_mass'),
          cathode_mass: optionalNumber(body.cathode_mass, 'cathode_mass'),
          anode_loading: optionalNumber(body.anode_loading, 'anode_loading'),
          cathode_loading: optionalNumber(body.cathode_loading, 'cathode_loading'),
          anode_thickness: optionalNumber(body.anode_thickness, 'anode_thickness'),
          cathode_thickness: optionalNumber(body.cathode_thickness, 'cathode_thickness'),
          anode_area: optionalNumber(body.anode_area, 'anode_area'),
          cathode_area: optionalNumber(body.cathode_area, 'cathode_area'),
          np_ratio: optionalNumber(body.np_ratio, 'np_ratio'),
          overhang_ratio: optionalNumber(body.overhang_ratio, 'overhang_ratio'),
          data_sources: normalizeDataSources(body),
        });

        return {
          status: 201,
          body: {
            data: serializeCell(cell.cell),
            data_sources: cell.dataSources.map(serializeDataSource),
          },
        };
      },
    },

    {
      method: 'GET',
      path: '/api/cells/:cellId',
      async handler(ctx) {
        const cellId = toSafeInt(ctx.params.cellId, 'cellId');
        const record = store.getCell(cellId);
        if (!record) {
          throw new HttpError(404, 'Cell not found');
        }

        return {
          status: 200,
          body: {
            data: serializeCell(record.cell),
            data_sources: record.dataSources.map(serializeDataSource),
          },
        };
      },
    },

    {
      method: 'PATCH',
      path: '/api/cells/:cellId',
      async handler(ctx) {
        const cellId = toSafeInt(ctx.params.cellId, 'cellId');
        const body = await readJsonBody(ctx.req);

        const updates = {};
        if (body.cell_name !== undefined) {
          updates.cell_name = requiredString(body.cell_name, 'cell_name', 255);
        }
        if (body.file_name !== undefined) {
          updates.file_name = optionalString(body.file_name, 'file_name', 255);
        }
        if (body.loading !== undefined) {
          updates.loading = optionalNumber(body.loading, 'loading');
        }
        if (body.active_material_pct !== undefined) {
          updates.active_material_pct = optionalNumber(body.active_material_pct, 'active_material_pct');
        }
        if (body.formation_cycles !== undefined) {
          updates.formation_cycles = optionalInteger(body.formation_cycles, 'formation_cycles');
        }
        if (body.test_number !== undefined) {
          updates.test_number = optionalString(body.test_number, 'test_number', 100);
        }
        if (body.electrolyte !== undefined) {
          updates.electrolyte = optionalString(body.electrolyte, 'electrolyte', 255);
        }
        if (body.substrate !== undefined) {
          updates.substrate = optionalString(body.substrate, 'substrate', 100);
        }
        if (body.separator !== undefined) {
          updates.separator = optionalString(body.separator, 'separator', 100);
        }
        if (body.formulation !== undefined) {
          updates.formulation = normalizeFormulation(body.formulation);
        }
        if (body.group_assignment !== undefined) {
          updates.group_assignment = optionalString(body.group_assignment, 'group_assignment', 100);
        }
        if (body.excluded !== undefined) {
          updates.excluded = optionalBoolean(body.excluded);
        }
        if (body.porosity !== undefined) {
          updates.porosity = optionalNumber(body.porosity, 'porosity');
        }
        if (body.cutoff_voltage_lower !== undefined) {
          updates.cutoff_voltage_lower = optionalNumber(body.cutoff_voltage_lower, 'cutoff_voltage_lower');
        }
        if (body.cutoff_voltage_upper !== undefined) {
          updates.cutoff_voltage_upper = optionalNumber(body.cutoff_voltage_upper, 'cutoff_voltage_upper');
        }
        if (body.anode_mass !== undefined) {
          updates.anode_mass = optionalNumber(body.anode_mass, 'anode_mass');
        }
        if (body.cathode_mass !== undefined) {
          updates.cathode_mass = optionalNumber(body.cathode_mass, 'cathode_mass');
        }
        if (body.anode_loading !== undefined) {
          updates.anode_loading = optionalNumber(body.anode_loading, 'anode_loading');
        }
        if (body.cathode_loading !== undefined) {
          updates.cathode_loading = optionalNumber(body.cathode_loading, 'cathode_loading');
        }
        if (body.anode_thickness !== undefined) {
          updates.anode_thickness = optionalNumber(body.anode_thickness, 'anode_thickness');
        }
        if (body.cathode_thickness !== undefined) {
          updates.cathode_thickness = optionalNumber(body.cathode_thickness, 'cathode_thickness');
        }
        if (body.anode_area !== undefined) {
          updates.anode_area = optionalNumber(body.anode_area, 'anode_area');
        }
        if (body.cathode_area !== undefined) {
          updates.cathode_area = optionalNumber(body.cathode_area, 'cathode_area');
        }
        if (body.np_ratio !== undefined) {
          updates.np_ratio = optionalNumber(body.np_ratio, 'np_ratio');
        }
        if (body.overhang_ratio !== undefined) {
          updates.overhang_ratio = optionalNumber(body.overhang_ratio, 'overhang_ratio');
        }

        if (
          body.data_sources !== undefined ||
          body.parquet_path !== undefined ||
          body.data_json !== undefined
        ) {
          updates.data_sources = normalizeDataSources(body);
        }

        const updated = store.updateCell(cellId, updates);
        if (!updated) {
          throw new HttpError(404, 'Cell not found');
        }

        return {
          status: 200,
          body: {
            data: serializeCell(updated.cell),
            data_sources: updated.dataSources.map(serializeDataSource),
          },
        };
      },
    },

    {
      method: 'DELETE',
      path: '/api/cells/:cellId',
      async handler(ctx) {
        const cellId = toSafeInt(ctx.params.cellId, 'cellId');
        const deleted = store.deleteCell(cellId);
        if (!deleted) {
          throw new HttpError(404, 'Cell not found');
        }

        return { status: 204, body: null };
      },
    },

    {
      method: 'GET',
      path: '/api/projects/:projectId/preferences',
      async handler(ctx) {
        const projectId = toSafeInt(ctx.params.projectId, 'projectId');
        const project = store.getProject(projectId);
        if (!project) {
          throw new HttpError(404, 'Project not found');
        }

        return {
          status: 200,
          body: {
            data: store.listProjectPreferences(projectId).map(serializePreference),
          },
        };
      },
    },

    {
      method: 'PUT',
      path: '/api/projects/:projectId/preferences/:preferenceKey',
      async handler(ctx) {
        const projectId = toSafeInt(ctx.params.projectId, 'projectId');
        const project = store.getProject(projectId);
        if (!project) {
          throw new HttpError(404, 'Project not found');
        }

        const preferenceKey = requiredString(ctx.params.preferenceKey, 'preferenceKey', 255);
        const body = await readJsonBody(ctx.req);

        const row = store.upsertProjectPreference(
          projectId,
          preferenceKey,
          jsonOrString(body.value),
        );

        return {
          status: 200,
          body: {
            data: serializePreference(row),
          },
        };
      },
    },
  ]);
}

export function createApp(overrides = {}) {
  const config = getConfig(overrides);
  const db = initDatabase(config.dbPath);
  const store = createStore(db);
  const router = buildRoutes(config, store);

  const server = http.createServer(async (req, res) => {
    try {
      if (req.method === 'OPTIONS') {
        writeNoContent(res, config.corsOrigin);
        return;
      }

      const baseUrl = `http://${req.headers.host ?? 'localhost'}`;
      const url = new URL(req.url ?? '/', baseUrl);

      const match = router.match(req.method ?? 'GET', url.pathname);
      if (!match) {
        writeJson(res, 404, { error: 'Route not found' }, config.corsOrigin);
        return;
      }

      const response = await match.route.handler({
        req,
        res,
        url,
        params: match.params,
      });

      if (response.status === 204) {
        writeNoContent(res, config.corsOrigin);
        return;
      }

      writeJson(res, response.status, response.body, config.corsOrigin);
    } catch (error) {
      if (error instanceof HttpError) {
        writeJson(
          res,
          error.status,
          { error: error.message, details: error.details },
          config.corsOrigin,
        );
        return;
      }

      writeJson(res, 500, { error: 'Internal server error' }, config.corsOrigin);
    }
  });

  server.on('close', () => {
    db.close();
  });

  return { server, config };
}
