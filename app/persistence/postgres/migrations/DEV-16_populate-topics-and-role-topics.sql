--
-- Migration DEV-16: Populate Topics and Role-Topics Mapping
--
-- Purpose: Seed the topics table with core CS fundamentals and role-specific
--          technical topics, then map them to appropriate roles via role_topics
--          junction table for interview template configuration.
-- Date: 2026-03-05
-- Module: app/question
-- Ticket: DEV-16
--
-- Changes:
--   1. Insert core CS fundamentals (CN, OS, OOPS, COA, DBMS, DSA)
--   2. Insert role-specific technical topics
--   3. Map topics to roles in role_topics table
--
-- Invariants preserved:
--   - All topics have scope='organization' (org-specific)
--   - All topics belong to organization_id=1 (super organization)
--   - Many-to-many relationship (topics can map to multiple roles)
--   - No SRS invariant broken (populating existing tables)
--   - No ERD invariant violated (valid FK relationships)
--
-- Rollback: See DEV-16_populate-topics-and-role-topics_rollback.sql
--

-- ============================================================================
-- PART 1: Populate topics table
-- ============================================================================

-- Core CS Fundamentals (IDs 1-6) - Essential for all university graduates
INSERT INTO public.topics (id, name, description, parent_topic_id, scope, organization_id, estimated_time_minutes)
VALUES
    -- Core CS Fundamentals
    (1, 'Computer Networks',
     'TCP/IP, HTTP/HTTPS, DNS, OSI model, network protocols, socket programming',
     NULL, 'organization', 1, 12),
    
    (2, 'Operating Systems',
     'Process management, threads, synchronization, memory management, file systems, deadlocks',
     NULL, 'organization', 1, 12),
    
    (3, 'Object-Oriented Programming',
     'Classes, objects, inheritance, polymorphism, encapsulation, abstraction, design patterns',
     NULL, 'organization', 1, 10),
    
    (4, 'Computer Organization and Architecture',
     'CPU architecture, instruction sets, memory hierarchy, pipelining, cache organization',
     NULL, 'organization', 1, 10),
    
    (5, 'Database Management Systems',
     'SQL, relational model, normalization, transactions, ACID properties, indexing, query optimization',
     NULL, 'organization', 1, 12),
    
    (6, 'Data Structures and Algorithms',
     'Arrays, linked lists, trees, graphs, sorting, searching, dynamic programming, complexity analysis',
     NULL, 'organization', 1, 15),

    -- Backend Development Topics (IDs 7-20)
    (7, 'RESTful APIs',
     'REST principles, HTTP methods, status codes, API design best practices, versioning',
     NULL, 'organization', 1, 10),
    
    (8, 'GraphQL',
     'GraphQL schema, queries, mutations, resolvers, Apollo, federation',
     NULL, 'organization', 1, 8),
    
    (9, 'Node.js',
     'Event loop, async/await, Express.js, middleware, streams, NPM ecosystem',
     NULL, 'organization', 1, 10),
    
    (10, 'Python',
     'Python syntax, Django, Flask, FastAPI, decorators, generators, async programming',
     NULL, 'organization', 1, 10),
    
    (11, 'Java',
     'Core Java, Spring Boot, JVM, multithreading, collections framework, JPA/Hibernate',
     NULL, 'organization', 1, 12),
    
    (12, 'Go',
     'Go syntax, goroutines, channels, Go modules, standard library, concurrency patterns',
     NULL, 'organization', 1, 10),
    
    (13, 'SQL Databases',
     'PostgreSQL, MySQL, query optimization, indexing strategies, stored procedures, triggers',
     5, 'organization', 1, 10),
    
    (14, 'NoSQL Databases',
     'MongoDB, Redis, Cassandra, DynamoDB, document stores, key-value stores, CAP theorem',
     NULL, 'organization', 1, 10),
    
    (15, 'Microservices Architecture',
     'Service decomposition, inter-service communication, API gateway, service mesh, distributed tracing',
     NULL, 'organization', 1, 12),
    
    (16, 'Message Queues',
     'RabbitMQ, Kafka, SQS, event-driven architecture, pub/sub patterns, message ordering',
     NULL, 'organization', 1, 10),
    
    (17, 'Caching Strategies',
     'Redis, Memcached, cache invalidation, CDN, browser caching, cache-aside pattern',
     NULL, 'organization', 1, 8),
    
    (18, 'API Security',
     'OAuth 2.0, JWT, API authentication, rate limiting, CORS, SQL injection prevention, XSS',
     NULL, 'organization', 1, 10),
    
    (19, 'Server-Side Performance',
     'Load balancing, horizontal scaling, database optimization, profiling, bottleneck analysis',
     NULL, 'organization', 1, 10),
    
    (20, 'Backend Testing',
     'Unit testing, integration testing, mocking, test coverage, TDD, API testing',
     NULL, 'organization', 1, 8),

    -- Frontend Development Topics (IDs 21-35)
    (21, 'JavaScript',
     'ES6+, closures, promises, async/await, prototypes, event loop, modules',
     NULL, 'organization', 1, 12),
    
    (22, 'TypeScript',
     'Type system, interfaces, generics, decorators, type inference, strict mode',
     NULL, 'organization', 1, 10),
    
    (23, 'React',
     'Components, hooks, state management, virtual DOM, JSX, React Router, context API',
     NULL, 'organization', 1, 12),
    
    (24, 'Vue.js',
     'Vue components, directives, Vuex, Vue Router, composition API, reactivity system',
     NULL, 'organization', 1, 10),
    
    (25, 'Angular',
     'Components, services, dependency injection, RxJS, routing, forms, Angular CLI',
     NULL, 'organization', 1, 12),
    
    (26, 'HTML/CSS',
     'Semantic HTML, CSS Grid, Flexbox, CSS animations, accessibility, browser compatibility',
     NULL, 'organization', 1, 8),
    
    (27, 'State Management',
     'Redux, MobX, Zustand, Recoil, global state, local state, state immutability',
     NULL, 'organization', 1, 10),
    
    (28, 'Web Performance Optimization',
     'Code splitting, lazy loading, bundle optimization, lighthouse scores, Core Web Vitals',
     NULL, 'organization', 1, 10),
    
    (29, 'Browser APIs',
     'DOM manipulation, Fetch API, Web Storage, Service Workers, WebSockets, Geolocation',
     NULL, 'organization', 1, 8),
    
    (30, 'Responsive Web Design',
     'Mobile-first design, media queries, viewport units, responsive images, progressive enhancement',
     NULL, 'organization', 1, 8),
    
    (31, 'Frontend Build Tools',
     'Webpack, Vite, Babel, npm/yarn, build optimization, development workflow',
     NULL, 'organization', 1, 6),
    
    (32, 'Frontend Testing',
     'Jest, React Testing Library, E2E testing with Cypress/Playwright, snapshot testing',
     NULL, 'organization', 1, 8),
    
    (33, 'CSS Frameworks',
     'Tailwind CSS, Bootstrap, Material-UI, Styled Components, CSS-in-JS',
     NULL, 'organization', 1, 6),
    
    (34, 'Web Accessibility',
     'WCAG guidelines, ARIA, screen readers, keyboard navigation, semantic markup',
     NULL, 'organization', 1, 8),
    
    (35, 'UI/UX Principles',
     'Design systems, user research, wireframing, prototyping, usability testing, interaction design',
     NULL, 'organization', 1, 10),

    -- DevOps Topics (IDs 36-50)
    (36, 'CI/CD Pipelines',
     'Jenkins, GitHub Actions, GitLab CI, Azure DevOps, deployment automation, pipeline optimization',
     NULL, 'organization', 1, 10),
    
    (37, 'Docker',
     'Containers, Dockerfile, Docker Compose, image optimization, multi-stage builds, Docker networking',
     NULL, 'organization', 1, 10),
    
    (38, 'Kubernetes',
     'Pods, services, deployments, ConfigMaps, secrets, Helm, Ingress, auto-scaling',
     NULL, 'organization', 1, 15),
    
    (39, 'AWS',
     'EC2, S3, RDS, Lambda, CloudFormation, VPC, IAM, CloudWatch, ECS/EKS',
     NULL, 'organization', 1, 12),
    
    (40, 'Azure',
     'Azure VMs, Azure Functions, Azure DevOps, ARM templates, Azure SQL, AKS',
     NULL, 'organization', 1, 12),
    
    (41, 'Google Cloud Platform',
     'Compute Engine, Cloud Functions, GKE, Cloud Storage, BigQuery, Cloud Run',
     NULL, 'organization', 1, 12),
    
    (42, 'Infrastructure as Code',
     'Terraform, Ansible, CloudFormation, Pulumi, configuration management, idempotency',
     NULL, 'organization', 1, 10),
    
    (43, 'Monitoring and Logging',
     'Prometheus, Grafana, ELK Stack, CloudWatch, application metrics, log aggregation',
     NULL, 'organization', 1, 10),
    
    (44, 'Linux System Administration',
     'Shell scripting, system services, package management, permissions, SSH, cron jobs',
     NULL, 'organization', 1, 10),
    
    (45, 'Networking Fundamentals',
     'Load balancers, DNS, VPN, firewalls, subnets, routing, network security',
     1, 'organization', 1, 10),
    
    (46, 'Version Control',
     'Git workflows, branching strategies, merge vs rebase, Git hooks, code review practices',
     NULL, 'organization', 1, 6),
    
    (47, 'Security Best Practices',
     'Secret management, vulnerability scanning, compliance, security hardening, zero-trust',
     NULL, 'organization', 1, 10),
    
    (48, 'Site Reliability Engineering',
     'SLOs/SLIs/SLAs, incident management, post-mortems, chaos engineering, on-call practices',
     NULL, 'organization', 1, 12),
    
    (49, 'Container Orchestration',
     'Docker Swarm, Nomad, container scheduling, service discovery, health checks',
     NULL, 'organization', 1, 10),
    
    (50, 'DevOps Culture',
     'Collaboration practices, automation mindset, continuous improvement, blameless culture',
     NULL, 'organization', 1, 6),

    -- Data Engineering Topics (IDs 51-63)
    (51, 'ETL/ELT Processes',
     'Data extraction, transformation, loading, data pipelines, batch vs streaming processing',
     NULL, 'organization', 1, 10),
    
    (52, 'Data Warehousing',
     'Snowflake, Redshift, BigQuery, star schema, fact tables, dimensional modeling',
     NULL, 'organization', 1, 12),
    
    (53, 'Apache Spark',
     'RDDs, DataFrames, Spark SQL, PySpark, distributed computing, Spark streaming',
     NULL, 'organization', 1, 12),
    
    (54, 'Apache Kafka',
     'Topics, partitions, producers, consumers, Kafka Streams, data streaming architecture',
     16, 'organization', 1, 10),
    
    (55, 'SQL Optimization',
     'Query tuning, execution plans, index strategies, partitioning, materialized views',
     13, 'organization', 1, 10),
    
    (56, 'Data Modeling',
     'Entity-relationship diagrams, normalization, denormalization, data vault, dimensional modeling',
     NULL, 'organization', 1, 10),
    
    (57, 'Big Data Technologies',
     'Hadoop, HDFS, MapReduce, Hive, Presto, distributed file systems',
     NULL, 'organization', 1, 12),
    
    (58, 'Data Quality',
     'Data validation, data cleansing, data profiling, schema validation, data governance',
     NULL, 'organization', 1, 8),
    
    (59, 'Workflow Orchestration',
     'Apache Airflow, Luigi, Prefect, DAGs, task dependencies, scheduling',
     NULL, 'organization', 1, 10),
    
    (60, 'Data Lake Architecture',
     'Data lake vs warehouse, Delta Lake, Iceberg, data organization, metadata management',
     NULL, 'organization', 1, 10),
    
    (61, 'Real-Time Data Processing',
     'Stream processing, event-driven architecture, Flink, Kinesis, real-time analytics',
     NULL, 'organization', 1, 10),
    
    (62, 'Data Visualization',
     'Tableau, Power BI, Looker, chart types, dashboard design, storytelling with data',
     NULL, 'organization', 1, 8),
    
    (63, 'Cloud Data Services',
     'AWS Glue, Azure Data Factory, GCP Dataflow, managed data services, serverless data',
     NULL, 'organization', 1, 10),

    -- Mobile Development Topics (IDs 64-75)
    (64, 'iOS Development',
     'Swift, UIKit, SwiftUI, Xcode, iOS SDK, App Store guidelines, iOS architecture',
     NULL, 'organization', 1, 12),
    
    (65, 'Android Development',
     'Kotlin, Android SDK, Jetpack Compose, Android Studio, Material Design, Play Store',
     NULL, 'organization', 1, 12),
    
    (66, 'React Native',
     'Cross-platform development, native modules, React Native CLI, Expo, bridging native code',
     NULL, 'organization', 1, 10),
    
    (67, 'Flutter',
     'Dart, widgets, state management, Flutter SDK, platform channels, Material/Cupertino',
     NULL, 'organization', 1, 10),
    
    (68, 'Mobile UI/UX',
     'Platform-specific patterns, navigation, touch interactions, mobile-first design',
     NULL, 'organization', 1, 8),
    
    (69, 'Mobile App Architecture',
     'MVVM, MVI, Clean Architecture, dependency injection, modularization',
     NULL, 'organization', 1, 10),
    
    (70, 'Mobile Storage',
     'SQLite, Realm, Core Data, SharedPreferences, async storage, local databases',
     NULL, 'organization', 1, 8),
    
    (71, 'Mobile Networking',
     'REST API consumption, GraphQL clients, network security, offline-first architecture',
     NULL, 'organization', 1, 8),
    
    (72, 'Mobile Testing',
     'XCTest, Espresso, Detox, Appium, UI testing, unit testing for mobile',
     NULL, 'organization', 1, 8),
    
    (73, 'Mobile Performance',
     'Memory management, battery optimization, app size reduction, rendering performance',
     NULL, 'organization', 1, 8),
    
    (74, 'Push Notifications',
     'FCM, APNS, notification strategies, deep linking, background tasks',
     NULL, 'organization', 1, 6),
    
    (75, 'Mobile DevOps',
     'Fastlane, App Center, Firebase, beta distribution, crash reporting, analytics',
     NULL, 'organization', 1, 8),

    -- Machine Learning Topics (IDs 76-90)
    (76, 'Machine Learning Fundamentals',
     'Supervised learning, unsupervised learning, regression, classification, model evaluation',
     NULL, 'organization', 1, 15),
    
    (77, 'Deep Learning',
     'Neural networks, CNNs, RNNs, transformers, backpropagation, activation functions',
     NULL, 'organization', 1, 15),
    
    (78, 'Python for ML',
     'NumPy, Pandas, Scikit-learn, data manipulation, feature engineering',
     10, 'organization', 1, 12),
    
    (79, 'TensorFlow',
     'TensorFlow 2.x, Keras, model building, training, deployment, TensorFlow Serving',
     NULL, 'organization', 1, 12),
    
    (80, 'PyTorch',
     'PyTorch tensors, autograd, model definition, training loops, torchvision, deployment',
     NULL, 'organization', 1, 12),
    
    (81, 'Model Deployment',
     'Model serving, REST APIs for models, Docker for ML, model versioning, A/B testing',
     NULL, 'organization', 1, 10),
    
    (82, 'MLOps',
     'ML pipelines, model monitoring, experiment tracking, feature stores, CI/CD for ML',
     NULL, 'organization', 1, 12),
    
    (83, 'Data Preprocessing',
     'Feature scaling, encoding, missing data handling, outlier detection, data augmentation',
     NULL, 'organization', 1, 8),
    
    (84, 'Natural Language Processing',
     'Text preprocessing, embeddings, BERT, GPT, sentiment analysis, named entity recognition',
     NULL, 'organization', 1, 12),
    
    (85, 'Computer Vision',
     'Image classification, object detection, segmentation, YOLO, ResNet, transfer learning',
     NULL, 'organization', 1, 12),
    
    (86, 'Model Optimization',
     'Hyperparameter tuning, model compression, quantization, pruning, knowledge distillation',
     NULL, 'organization', 1, 10),
    
    (87, 'ML System Design',
     'Training infrastructure, data versioning, model registry, feature engineering pipelines',
     NULL, 'organization', 1, 12),
    
    (88, 'Reinforcement Learning',
     'Q-learning, policy gradients, reward functions, exploration vs exploitation',
     NULL, 'organization', 1, 10),
    
    (89, 'Time Series Analysis',
     'ARIMA, LSTMs for sequences, forecasting, anomaly detection in time series',
     NULL, 'organization', 1, 10),
    
    (90, 'ML Ethics and Bias',
     'Fairness in ML, bias detection, explainability, responsible AI, privacy-preserving ML',
     NULL, 'organization', 1, 8),

    -- System Design Topics (IDs 91-100)
    (91, 'System Design Fundamentals',
     'Scalability, availability, reliability, CAP theorem, consistency models, trade-offs',
     NULL, 'organization', 1, 15),
    
    (92, 'Distributed Systems',
     'Consensus algorithms, replication, partitioning, distributed transactions, eventual consistency',
     NULL, 'organization', 1, 15),
    
    (93, 'API Design',
     'API versioning, pagination, rate limiting, error handling, API documentation',
     NULL, 'organization', 1, 10),
    
    (94, 'Database Design',
     'Schema design, indexing strategies, sharding, replication, read replicas, database selection',
     5, 'organization', 1, 12),
    
    (95, 'Caching Architecture',
     'Cache placement, eviction policies, distributed caching, cache consistency, write strategies',
     17, 'organization', 1, 10),
    
    (96, 'Load Balancing',
     'Load balancing algorithms, health checks, sticky sessions, L4 vs L7 balancing',
     NULL, 'organization', 1, 8),
    
    (97, 'Asynchronous Processing',
     'Message queues, task queues, background jobs, event sourcing, CQRS',
     NULL, 'organization', 1, 10),
    
    (98, 'High Availability',
     'Failover strategies, redundancy, disaster recovery, multi-region deployment',
     NULL, 'organization', 1, 10),
    
    (99, 'Observability',
     'Logging, metrics, tracing, alerting, debugging distributed systems',
     NULL, 'organization', 1, 10),
    
    (100, 'Security Architecture',
     'Authentication, authorization, encryption, secure communication, threat modeling',
     NULL, 'organization', 1, 10),

    -- QA/Testing Topics (IDs 101-108)
    (101, 'Test Automation',
     'Selenium, automation frameworks, test scripts, CI integration, test maintenance',
     NULL, 'organization', 1, 10),
    
    (102, 'API Testing',
     'Postman, REST Assured, API test automation, contract testing, performance testing',
     NULL, 'organization', 1, 8),
    
    (103, 'Performance Testing',
     'JMeter, load testing, stress testing, benchmarking, performance metrics',
     NULL, 'organization', 1, 10),
    
    (104, 'Test Planning',
     'Test strategies, test cases, test coverage, risk-based testing, test documentation',
     NULL, 'organization', 1, 8),
    
    (105, 'Mobile Testing',
     'Appium, device testing, cross-platform testing, mobile test automation',
     NULL, 'organization', 1, 8),
    
    (106, 'Security Testing',
     'Penetration testing, vulnerability assessment, OWASP, security tools',
     NULL, 'organization', 1, 10),
    
    (107, 'Continuous Testing',
     'Test automation in CI/CD, shift-left testing, test feedback loops',
     NULL, 'organization', 1, 8),
    
    (108, 'Quality Assurance Principles',
     'QA methodologies, defect lifecycle, quality metrics, testing best practices',
     NULL, 'organization', 1, 8),

    -- Cloud Engineering Topics (IDs 109-115)
    (109, 'Cloud Architecture Patterns',
     'Serverless, microservices on cloud, multi-cloud, cloud-native design',
     NULL, 'organization', 1, 12),
    
    (110, 'Cloud Security',
     'IAM, encryption at rest/in transit, VPC, security groups, compliance, cloud-native security',
     NULL, 'organization', 1, 10),
    
    (111, 'Cloud Cost Optimization',
     'Resource tagging, reserved instances, auto-scaling, cost monitoring, FinOps',
     NULL, 'organization', 1, 8),
    
    (112, 'Serverless Architecture',
     'AWS Lambda, Azure Functions, Google Cloud Functions, serverless frameworks, FaaS patterns',
     NULL, 'organization', 1, 10),
    
    (113, 'Cloud Migration',
     'Lift and shift, re-platforming, cloud adoption strategies, migration patterns',
     NULL, 'organization', 1, 10),
    
    (114, 'Cloud Networking',
     'VPC design, hybrid cloud, VPN, Direct Connect, cloud interconnects',
     NULL, 'organization', 1, 10),
    
    (115, 'Multi-Cloud Strategy',
     'Cloud portability, vendor lock-in avoidance, multi-cloud management',
     NULL, 'organization', 1, 8),

    -- Design Topics (IDs 116-120)
    (116, 'Design Systems',
     'Component libraries, design tokens, style guides, design-dev collaboration',
     NULL, 'organization', 1, 8),
    
    (117, 'User Research',
     'User interviews, surveys, personas, user journey mapping, usability testing',
     NULL, 'organization', 1, 10),
    
    (118, 'Prototyping',
     'Wireframing, mockups, interactive prototypes, Figma, Sketch, Adobe XD',
     NULL, 'organization', 1, 8),
    
    (119, 'Interaction Design',
     'Micro-interactions, animations, transitions, user feedback, design patterns',
     NULL, 'organization', 1, 8),
    
    (120, 'Visual Design',
     'Typography, color theory, layout, composition, design principles',
     NULL, 'organization', 1, 8)

ON CONFLICT DO NOTHING;

-- ============================================================================
-- PART 2: Map topics to roles in role_topics table
-- ============================================================================

INSERT INTO public.role_topics (role_id, topic_id)
VALUES
    -- Backend Developer (role_id=1) - Core CS + Backend specific
    (1, 1),   -- Computer Networks
    (1, 2),   -- Operating Systems
    (1, 3),   -- Object-Oriented Programming
    (1, 5),   -- Database Management Systems
    (1, 6),   -- Data Structures and Algorithms
    (1, 7),   -- RESTful APIs
    (1, 8),   -- GraphQL
    (1, 9),   -- Node.js
    (1, 10),  -- Python
    (1, 11),  -- Java
    (1, 12),  -- Go
    (1, 13),  -- SQL Databases
    (1, 14),  -- NoSQL Databases
    (1, 15),  -- Microservices Architecture
    (1, 16),  -- Message Queues
    (1, 17),  -- Caching Strategies
    (1, 18),  -- API Security
    (1, 19),  -- Server-Side Performance
    (1, 20),  -- Backend Testing
    (1, 46),  -- Version Control
    (1, 91),  -- System Design Fundamentals
    (1, 92),  -- Distributed Systems
    (1, 93),  -- API Design
    (1, 94),  -- Database Design
    (1, 95),  -- Caching Architecture

    -- Frontend Developer (role_id=2) - Core CS + Frontend specific
    (2, 3),   -- Object-Oriented Programming
    (2, 6),   -- Data Structures and Algorithms
    (2, 21),  -- JavaScript
    (2, 22),  -- TypeScript
    (2, 23),  -- React
    (2, 24),  -- Vue.js
    (2, 25),  -- Angular
    (2, 26),  -- HTML/CSS
    (2, 27),  -- State Management
    (2, 28),  -- Web Performance Optimization
    (2, 29),  -- Browser APIs
    (2, 30),  -- Responsive Web Design
    (2, 31),  -- Frontend Build Tools
    (2, 32),  -- Frontend Testing
    (2, 33),  -- CSS Frameworks
    (2, 34),  -- Web Accessibility
    (2, 35),  -- UI/UX Principles
    (2, 46),  -- Version Control
    (2, 116), -- Design Systems
    (2, 118), -- Prototyping
    (2, 119), -- Interaction Design

    -- Full Stack Developer (role_id=3) - All CS fundamentals + both stacks + system design
    (3, 1),   -- Computer Networks
    (3, 2),   -- Operating Systems
    (3, 3),   -- Object-Oriented Programming
    (3, 5),   -- Database Management Systems
    (3, 6),   -- Data Structures and Algorithms
    (3, 7),   -- RESTful APIs
    (3, 8),   -- GraphQL
    (3, 9),   -- Node.js
    (3, 10),  -- Python
    (3, 13),  -- SQL Databases
    (3, 14),  -- NoSQL Databases
    (3, 15),  -- Microservices Architecture
    (3, 17),  -- Caching Strategies
    (3, 18),  -- API Security
    (3, 21),  -- JavaScript
    (3, 22),  -- TypeScript
    (3, 23),  -- React
    (3, 24),  -- Vue.js
    (3, 26),  -- HTML/CSS
    (3, 27),  -- State Management
    (3, 28),  -- Web Performance Optimization
    (3, 30),  -- Responsive Web Design
    (3, 37),  -- Docker
    (3, 46),  -- Version Control
    (3, 91),  -- System Design Fundamentals
    (3, 92),  -- Distributed Systems
    (3, 93),  -- API Design
    (3, 94),  -- Database Design

    -- DevOps Engineer (role_id=4) - OS + Networks + DevOps specific
    (4, 1),   -- Computer Networks
    (4, 2),   -- Operating Systems
    (4, 4),   -- Computer Organization and Architecture
    (4, 6),   -- Data Structures and Algorithms
    (4, 36),  -- CI/CD Pipelines
    (4, 37),  -- Docker
    (4, 38),  -- Kubernetes
    (4, 39),  -- AWS
    (4, 40),  -- Azure
    (4, 41),  -- Google Cloud Platform
    (4, 42),  -- Infrastructure as Code
    (4, 43),  -- Monitoring and Logging
    (4, 44),  -- Linux System Administration
    (4, 45),  -- Networking Fundamentals
    (4, 46),  -- Version Control
    (4, 47),  -- Security Best Practices
    (4, 48),  -- Site Reliability Engineering
    (4, 49),  -- Container Orchestration
    (4, 50),  -- DevOps Culture
    (4, 91),  -- System Design Fundamentals
    (4, 96),  -- Load Balancing
    (4, 98),  -- High Availability
    (4, 99),  -- Observability
    (4, 109), -- Cloud Architecture Patterns
    (4, 110), -- Cloud Security

    -- Data Engineer (role_id=5) - DBMS + DSA + Data Engineering specific
    (5, 2),   -- Operating Systems
    (5, 5),   -- Database Management Systems
    (5, 6),   -- Data Structures and Algorithms
    (5, 10),  -- Python
    (5, 13),  -- SQL Databases
    (5, 14),  -- NoSQL Databases
    (5, 46),  -- Version Control
    (5, 51),  -- ETL/ELT Processes
    (5, 52),  -- Data Warehousing
    (5, 53),  -- Apache Spark
    (5, 54),  -- Apache Kafka
    (5, 55),  -- SQL Optimization
    (5, 56),  -- Data Modeling
    (5, 57),  -- Big Data Technologies
    (5, 58),  -- Data Quality
    (5, 59),  -- Workflow Orchestration
    (5, 60),  -- Data Lake Architecture
    (5, 61),  -- Real-Time Data Processing
    (5, 62),  -- Data Visualization
    (5, 63),  -- Cloud Data Services
    (5, 92),  -- Distributed Systems

    -- Mobile App Developer (role_id=6) - OOPS + DSA + Mobile specific
    (6, 3),   -- Object-Oriented Programming
    (6, 6),   -- Data Structures and Algorithms
    (6, 46),  -- Version Control
    (6, 64),  -- iOS Development
    (6, 65),  -- Android Development
    (6, 66),  -- React Native
    (6, 67),  -- Flutter
    (6, 68),  -- Mobile UI/UX
    (6, 69),  -- Mobile App Architecture
    (6, 70),  -- Mobile Storage
    (6, 71),  -- Mobile Networking
    (6, 72),  -- Mobile Testing
    (6, 73),  -- Mobile Performance
    (6, 74),  -- Push Notifications
    (6, 75),  -- Mobile DevOps
    (6, 93),  -- API Design
    (6, 116), -- Design Systems
    (6, 35),  -- UI/UX Principles

    -- ML Engineer (role_id=7) - DSA + DBMS + OS + ML specific
    (7, 2),   -- Operating Systems
    (7, 5),   -- Database Management Systems
    (7, 6),   -- Data Structures and Algorithms
    (7, 10),  -- Python
    (7, 46),  -- Version Control
    (7, 76),  -- Machine Learning Fundamentals
    (7, 77),  -- Deep Learning
    (7, 78),  -- Python for ML
    (7, 79),  -- TensorFlow
    (7, 80),  -- PyTorch
    (7, 81),  -- Model Deployment
    (7, 82),  -- MLOps
    (7, 83),  -- Data Preprocessing
    (7, 84),  -- Natural Language Processing
    (7, 85),  -- Computer Vision
    (7, 86),  -- Model Optimization
    (7, 87),  -- ML System Design
    (7, 88),  -- Reinforcement Learning
    (7, 89),  -- Time Series Analysis
    (7, 90),  -- ML Ethics and Bias
    (7, 37),  -- Docker
    (7, 92)   -- Distributed Systems

ON CONFLICT (role_id, topic_id) DO NOTHING;

-- ============================================================================
-- PART 3: Update sequence to continue from ID 121
-- ============================================================================

-- Ensure the sequence starts from 121 for future topic insertions
SELECT setval('public.topics_id_seq', 120, true);

