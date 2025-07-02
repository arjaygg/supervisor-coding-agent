-- supervisor_agent/db/schema_extensions.sql

-- Resource allocation tracking
CREATE TABLE IF NOT EXISTS resource_allocations (
    id SERIAL PRIMARY KEY,
    task_id INTEGER,
    provider_id VARCHAR(50),
    resource_type VARCHAR(50) NOT NULL,
    allocated_amount DECIMAL NOT NULL,
    allocation_time TIMESTAMP DEFAULT NOW(),
    deallocation_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active'
);

-- Resource conflicts
CREATE TABLE IF NOT EXISTS resource_conflicts (
    id SERIAL PRIMARY KEY,
    conflict_type VARCHAR(50) NOT NULL,
    affected_tasks INTEGER[],
    affected_providers VARCHAR(50)[],
    resolution_strategy VARCHAR(100),
    detected_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending'
);

-- Resource reservations
CREATE TABLE IF NOT EXISTS resource_reservations (
    id SERIAL PRIMARY KEY,
    task_id INTEGER,
    resource_type VARCHAR(50) NOT NULL,
    reserved_amount DECIMAL NOT NULL,
    reservation_start TIMESTAMP NOT NULL,
    reservation_end TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'active'
);
