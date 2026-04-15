-- FL client topology node name for graph/threat-map scoping

ALTER TABLE fl_clients
  ADD COLUMN IF NOT EXISTS node_name TEXT;
