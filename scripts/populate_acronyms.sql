-- Populate acronyms table with curated technical acronyms
-- Run this after the acronyms table migration has been applied

-- AI/ML acronyms
INSERT INTO acronyms (acronym, definition, confidence_score, source_documents, is_verified) VALUES
('AI', 'Artificial Intelligence', 0.9, ARRAY['curated_technical_terms'], true),
('ML', 'Machine Learning', 0.9, ARRAY['curated_technical_terms'], true),
('NLP', 'Natural Language Processing', 0.9, ARRAY['curated_technical_terms'], true),
('LLM', 'Large Language Model', 0.9, ARRAY['curated_technical_terms'], true),
('RAG', 'Retrieval-Augmented Generation', 0.9, ARRAY['curated_technical_terms'], true),
('BERT', 'Bidirectional Encoder Representations from Transformers', 0.9, ARRAY['curated_technical_terms'], true),
('GPT', 'Generative Pre-trained Transformer', 0.9, ARRAY['curated_technical_terms'], true),
('CNN', 'Convolutional Neural Network', 0.9, ARRAY['curated_technical_terms'], true),
('RNN', 'Recurrent Neural Network', 0.9, ARRAY['curated_technical_terms'], true),
('LSTM', 'Long Short-Term Memory', 0.9, ARRAY['curated_technical_terms'], true),
('GAN', 'Generative Adversarial Network', 0.9, ARRAY['curated_technical_terms'], true),
('RL', 'Reinforcement Learning', 0.9, ARRAY['curated_technical_terms'], true),
('DL', 'Deep Learning', 0.9, ARRAY['curated_technical_terms'], true),

-- Software Development
('API', 'Application Programming Interface', 0.9, ARRAY['curated_technical_terms'], true),
('REST', 'Representational State Transfer', 0.9, ARRAY['curated_technical_terms'], true),
('JSON', 'JavaScript Object Notation', 0.9, ARRAY['curated_technical_terms'], true),
('XML', 'Extensible Markup Language', 0.9, ARRAY['curated_technical_terms'], true),
('SQL', 'Structured Query Language', 0.9, ARRAY['curated_technical_terms'], true),
('NoSQL', 'Not Only SQL', 0.9, ARRAY['curated_technical_terms'], true),
('ORM', 'Object-Relational Mapping', 0.9, ARRAY['curated_technical_terms'], true),
('MVC', 'Model-View-Controller', 0.9, ARRAY['curated_technical_terms'], true),
('CRUD', 'Create, Read, Update, Delete', 0.9, ARRAY['curated_technical_terms'], true),
('CI', 'Continuous Integration', 0.9, ARRAY['curated_technical_terms'], true),
('CD', 'Continuous Deployment', 0.9, ARRAY['curated_technical_terms'], true),
('DevOps', 'Development Operations', 0.9, ARRAY['curated_technical_terms'], true),
('TDD', 'Test-Driven Development', 0.9, ARRAY['curated_technical_terms'], true),
('BDD', 'Behavior-Driven Development', 0.9, ARRAY['curated_technical_terms'], true),

-- Web Technologies
('HTTP', 'Hypertext Transfer Protocol', 0.9, ARRAY['curated_technical_terms'], true),
('HTTPS', 'Hypertext Transfer Protocol Secure', 0.9, ARRAY['curated_technical_terms'], true),
('HTML', 'Hypertext Markup Language', 0.9, ARRAY['curated_technical_terms'], true),
('CSS', 'Cascading Style Sheets', 0.9, ARRAY['curated_technical_terms'], true),
('JS', 'JavaScript', 0.9, ARRAY['curated_technical_terms'], true),
('DOM', 'Document Object Model', 0.9, ARRAY['curated_technical_terms'], true),
('AJAX', 'Asynchronous JavaScript and XML', 0.9, ARRAY['curated_technical_terms'], true),
('SPA', 'Single Page Application', 0.9, ARRAY['curated_technical_terms'], true),
('PWA', 'Progressive Web Application', 0.9, ARRAY['curated_technical_terms'], true),

-- Databases
('DB', 'Database', 0.9, ARRAY['curated_technical_terms'], true),
('RDBMS', 'Relational Database Management System', 0.9, ARRAY['curated_technical_terms'], true),
('ACID', 'Atomicity, Consistency, Isolation, Durability', 0.9, ARRAY['curated_technical_terms'], true),
('CAP', 'Consistency, Availability, Partition Tolerance', 0.9, ARRAY['curated_technical_terms'], true),
('BASE', 'Basically Available, Soft State, Eventually Consistent', 0.9, ARRAY['curated_technical_terms'], true),
('OLTP', 'Online Transaction Processing', 0.9, ARRAY['curated_technical_terms'], true),
('OLAP', 'Online Analytical Processing', 0.9, ARRAY['curated_technical_terms'], true),
('ETL', 'Extract, Transform, Load', 0.9, ARRAY['curated_technical_terms'], true),

-- Cloud Computing
('IaaS', 'Infrastructure as a Service', 0.9, ARRAY['curated_technical_terms'], true),
('PaaS', 'Platform as a Service', 0.9, ARRAY['curated_technical_terms'], true),
('SaaS', 'Software as a Service', 0.9, ARRAY['curated_technical_terms'], true),
('AWS', 'Amazon Web Services', 0.9, ARRAY['curated_technical_terms'], true),
('GCP', 'Google Cloud Platform', 0.9, ARRAY['curated_technical_terms'], true),
('Azure', 'Microsoft Azure', 0.9, ARRAY['curated_technical_terms'], true),
('Docker', 'Container Platform', 0.9, ARRAY['curated_technical_terms'], true),
('Kubernetes', 'Container Orchestration System', 0.9, ARRAY['curated_technical_terms'], true),

-- Networking
('TCP', 'Transmission Control Protocol', 0.9, ARRAY['curated_technical_terms'], true),
('UDP', 'User Datagram Protocol', 0.9, ARRAY['curated_technical_terms'], true),
('IP', 'Internet Protocol', 0.9, ARRAY['curated_technical_terms'], true),
('DNS', 'Domain Name System', 0.9, ARRAY['curated_technical_terms'], true),
('VPN', 'Virtual Private Network', 0.9, ARRAY['curated_technical_terms'], true),
('LAN', 'Local Area Network', 0.9, ARRAY['curated_technical_terms'], true),
('WAN', 'Wide Area Network', 0.9, ARRAY['curated_technical_terms'], true),
('NAT', 'Network Address Translation', 0.9, ARRAY['curated_technical_terms'], true),
('DHCP', 'Dynamic Host Configuration Protocol', 0.9, ARRAY['curated_technical_terms'], true),

-- Security
('SSL', 'Secure Sockets Layer', 0.9, ARRAY['curated_technical_terms'], true),
('TLS', 'Transport Layer Security', 0.9, ARRAY['curated_technical_terms'], true),
('OAuth', 'Open Authorization', 0.9, ARRAY['curated_technical_terms'], true),
('JWT', 'JSON Web Token', 0.9, ARRAY['curated_technical_terms'], true),
('RBAC', 'Role-Based Access Control', 0.9, ARRAY['curated_technical_terms'], true),
('ACL', 'Access Control List', 0.9, ARRAY['curated_technical_terms'], true),
('PKI', 'Public Key Infrastructure', 0.9, ARRAY['curated_technical_terms'], true),
('AES', 'Advanced Encryption Standard', 0.9, ARRAY['curated_technical_terms'], true),

-- Data Formats
('CSV', 'Comma-Separated Values', 0.9, ARRAY['curated_technical_terms'], true),
('YAML', 'YAML Ain''t Markup Language', 0.9, ARRAY['curated_technical_terms'], true),
('TOML', 'Tom''s Obvious Minimal Language', 0.9, ARRAY['curated_technical_terms'], true),
('PDF', 'Portable Document Format', 0.9, ARRAY['curated_technical_terms'], true),
('OCR', 'Optical Character Recognition', 0.9, ARRAY['curated_technical_terms'], true),

-- Technical Service Assistant specific
('RNI', 'Radio Network Interface', 0.9, ARRAY['curated_technical_terms'], true),
('AMI', 'Advanced Metering Infrastructure', 0.9, ARRAY['curated_technical_terms'], true),
('ESM', 'Energy Services Module', 0.9, ARRAY['curated_technical_terms'], true),
('MDM', 'Meter Data Management', 0.9, ARRAY['curated_technical_terms'], true),
('HAN', 'Home Area Network', 0.9, ARRAY['curated_technical_terms'], true),
('DA', 'Distribution Automation', 0.9, ARRAY['curated_technical_terms'], true),
('DER', 'Distributed Energy Resources', 0.9, ARRAY['curated_technical_terms'], true),
('DR', 'Demand Response', 0.9, ARRAY['curated_technical_terms'], true),
('EMS', 'Energy Management System', 0.9, ARRAY['curated_technical_terms'], true),
('FDIR', 'Fault Detection, Isolation and Restoration', 0.9, ARRAY['curated_technical_terms'], true),
('GIS', 'Geographic Information System', 0.9, ARRAY['curated_technical_terms'], true),
('HMI', 'Human-Machine Interface', 0.9, ARRAY['curated_technical_terms'], true),
('IEC', 'International Electrotechnical Commission', 0.9, ARRAY['curated_technical_terms'], true),
('IoT', 'Internet of Things', 0.9, ARRAY['curated_technical_terms'], true),
('PLC', 'Programmable Logic Controller', 0.9, ARRAY['curated_technical_terms'], true),
('SCADA', 'Supervisory Control and Data Acquisition', 0.9, ARRAY['curated_technical_terms'], true),
('SOE', 'Sequence of Events', 0.9, ARRAY['curated_technical_terms'], true),
('TMR', 'Trip Matrix Recorder', 0.9, ARRAY['curated_technical_terms'], true),
('VVO', 'Volt-VAR Optimization', 0.9, ARRAY['curated_technical_terms'], true)

ON CONFLICT (acronym) DO NOTHING;

-- Update the ACRONYM_INDEX.md file with the inserted acronyms
-- This would be done by the Python script, but for now we'll document it
