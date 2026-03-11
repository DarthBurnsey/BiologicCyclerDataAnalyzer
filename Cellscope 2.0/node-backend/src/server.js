import { createApp } from './app.js';

const { server, config } = createApp();

server.listen(config.port, () => {
  console.log(`CellScope 2.0 Node API running on http://localhost:${config.port}`);
});

function shutdown(signal) {
  console.log(`Received ${signal}. Shutting down...`);
  server.close(() => {
    process.exit(0);
  });
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
