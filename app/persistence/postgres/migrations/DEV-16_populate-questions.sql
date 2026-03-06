--
-- Migration DEV-16: Populate Questions and Question-Topics Mapping
--
-- Purpose: Seed the questions table with interview-standard technical questions
--          for all topics associated with at least one developer role.
--          Distribution: 1 easy, 3 medium, 1 hard per topic.
-- Date: 2026-03-05
-- Module: app/question
-- Ticket: DEV-16
--
-- Changes:
--   1. Insert 515 high-quality interview questions (103 topics × 5 questions)
--   2. Populate question_topics relation mapping
--   3. Exclude QA topics (101-108) as no QA role exists
--
-- Invariants preserved:
--   - All questions have scope='organization' (org-specific)
--   - All questions belong to organization_id=1 (super organization)
--   - Question types: 'technical' for most, 'behavioral' for soft-skill topics
--   - Explicit IDs for deterministic references
--   - No SRS/ERD invariants violated
--
-- Rollback: See DEV-16_populate-questions_rollback.sql
--

-- ============================================================================
-- CLEANUP: Remove existing questions from partial runs (idempotent)
-- ============================================================================
DELETE FROM public.questions WHERE id BETWEEN 1 AND 515;

-- ============================================================================
-- PART 1: Populate questions for Core CS Fundamentals (Topics 1-6)
-- ============================================================================

INSERT INTO public.questions (id, question_text, answer_text, question_type, difficulty, scope, organization_id, source_type, estimated_time_minutes, is_active)
VALUES
    -- Topic 1: Computer Networks (5 questions)
    (1, 'What is the difference between TCP and UDP? When would you use each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 5, true),
    
    (2, 'Explain the OSI model layers and their functions. How does data flow through these layers?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (3, 'How does the three-way handshake work in TCP? What happens if the third ACK is lost?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (4, 'Design a solution to detect and diagnose network latency issues in a distributed microservices architecture.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (5, 'Explain how BGP works and discuss a scenario where BGP hijacking could occur. How would you detect and prevent it?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 20, true),

    -- Topic 2: Operating Systems (5 questions)
    (6, 'What is the difference between a process and a thread?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 5, true),
    
    (7, 'Explain the different CPU scheduling algorithms and their use cases.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (8, 'What is a deadlock? Explain the four necessary conditions and strategies to prevent/avoid/detect deadlocks.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (9, 'Explain virtual memory, paging, and how page replacement algorithms like LRU work.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (10, 'You have a high-traffic database system where readers vastly outnumber writers, but writes are critical. Compare different synchronization strategies for the readers-writers problem. What are the starvation risks and how would you choose between reader-preference, writer-preference, and fair queuing approaches?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 3: Object-Oriented Programming (5 questions)
    (11, 'Explain the four pillars of Object-Oriented Programming with examples.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 7, true),
    
    (12, 'What is the difference between abstract classes and interfaces? When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (13, 'Explain the SOLID principles and provide an example of violating and then fixing the Liskov Substitution Principle.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (14, 'Compare and contrast composition vs inheritance. Provide a real-world scenario where composition is preferred.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (15, 'You need to design a parking lot management system with different spot sizes, multiple payment methods, and real-time availability tracking. Discuss how you would apply OOP principles (inheritance vs composition, abstraction, polymorphism) and which design patterns would be appropriate. What are the trade-offs between different architectural approaches?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 4: Computer Organization and Architecture (5 questions)
    (16, 'Explain the difference between Von Neumann and Harvard architecture.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 7, true),
    
    (17, 'Explain the memory hierarchy and the principle of locality. How do caches exploit locality?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (18, 'What is pipelining in CPU architecture? Explain pipeline hazards and how they are resolved.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (19, 'Explain cache coherence in multi-core systems and the MESI protocol.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (20, 'A company wants to build a specialized processor for real-time image processing (filters, edge detection, color conversion). Discuss the architectural trade-offs between using a general-purpose CPU, GPU, FPGA, or designing a custom ASIC. What instruction set features would be most valuable and why?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 5: Database Management Systems (5 questions)
    (21, 'Explain ACID properties in databases with examples.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 7, true),
    
    (22, 'What are database indexes? Explain B-tree and Hash indexes and their use cases.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (23, 'Explain different isolation levels and the problems they solve (dirty read, non-repeatable read, phantom read).',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (24, 'Explain database normalization forms (1NF, 2NF, 3NF, BCNF) and when denormalization might be appropriate.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (25, 'You''re building a multi-tenant SaaS application expecting to scale from 10 to 10,000 customers. Compare the trade-offs between shared schema, schema-per-tenant, and database-per-tenant approaches. How would you choose between different sharding strategies and what are the implications for billing, compliance, and data migration?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 6: Data Structures and Algorithms (5 questions)
    (26, 'Explain the difference between an array and a linked list. When would you use each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 5, true),
    
    (27, 'Explain how a hash table works, including collision resolution strategies.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (28, 'Compare quicksort, mergesort, and heapsort. Analyze time/space complexity and stability.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (29, 'Explain graph traversal algorithms (BFS, DFS) and their applications. Provide time complexity analysis.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (30, 'Explain the data structure combination needed to build an LRU cache with O(1) get and put operations. Why is this combination necessary and what would be the trade-offs of using alternative approaches like a simple hash map with timestamps or a sorted tree?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- ============================================================================
    -- PART 2: Backend Engineering Topics (Topics 7-20)
    -- ============================================================================

    -- Topic 7: RESTful APIs (5 questions)
    (31, 'What are the key principles of RESTful API design?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 7, true),
    
    (32, 'Explain the difference between PUT and PATCH. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (33, 'How would you implement API rate limiting? Discuss different algorithms and their trade-offs.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (34, 'Design a RESTful API for a social media platform including posts, comments, likes, and follows. Include authentication and authorization.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 20, true),
    
    (35, 'Your API serves millions of users across mobile apps,web clients, and third-party integrations. Compare URI versioning (/v1/), header versioning, and query parameter approaches. How would you manage a breaking change rollout without disrupting existing clients? What are the risks of maintaining too many versions?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 8: GraphQL (5 questions)
    (36, 'What is GraphQL and how does it differ from REST?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 8, true),
    
    (37, 'Explain the N+1 query problem in GraphQL and how to solve it using DataLoader.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (38, 'How would you implement authentication and authorization in GraphQL? Compare field-level vs query-level authorization.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (39, 'Design a GraphQL schema for an e-commerce platform with products, users, orders, and reviews. Include mutations and subscriptions.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 20, true),
    
    (40, 'GraphQL APIs are vulnerable to malicious queries that could overwhelm your servers (deeply nested queries, circular references, expensive array fields). Compare different protection strategies: query depth limiting, complexity cost analysis, timeout limits, and query allowlisting. What are the trade-offs of each approach and how would you balance security with legitimate use cases?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 9: Node.js (5 questions)
    (41, 'Explain the event loop in Node.js and how asynchronous I/O works.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 10, true),
    
    (42, 'Compare callbacks, promises, and async/await in Node.js. What is callback hell and how do you avoid it?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (43, 'How would you handle CPU-intensive tasks in Node.js without blocking the event loop?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (44, 'Explain memory management and garbage collection in Node.js. How would you debug memory leaks?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (45, 'You need to build a real-time chat system handling millions of concurrent users with features like typing indicators, presence, and message persistence. Discuss the architectural challenges of horizontal scaling WebSocket connections. How do you handle message routing between server instances, ensure message ordering, and manage connection failover?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 10: Python (5 questions)
    (46, 'Explain Python''s GIL (Global Interpreter Lock) and its implications for multi-threading.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 8, true),
    
    (47, 'Compare list comprehensions, generator expressions, and map/filter. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (48, 'Explain Python decorators. Implement a decorator for caching function results (memoization) and rate limiting.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (49, 'How does Python''s garbage collection work? Explain reference counting and cycle detection.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (50, 'Your Python application has both I/O-bound operations (database queries, API calls) and CPU-intensive tasks (image processing, data analysis). Discuss the challenges of mixing synchronous and asynchronous code. How would you architect the application to leverage async for I/O while handling blocking operations? What are the risks and how do you prevent async performance degradation?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 11: Java (5 questions)
    (51, 'Explain the difference between JVM, JRE, and JDK.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 5, true),
    
    (52, 'Explain Java memory model: heap, stack, and garbage collection algorithms.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (53, 'Compare Java Streams API with traditional loops. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (54, 'Explain the Java Executor framework and different thread pool types. How would you choose the right one?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (55, 'Your Java application has a configuration manager that must be instantiated exactly once and accessed from multiple threads simultaneously. The initialization is expensive (reads from database and external config files). Discuss the trade-offs between different singleton implementation approaches: eager initialization, synchronized getInstance(), double-checked locking, and enum-based singletons. What are the memory visibility concerns and how does the Java Memory Model affect your choice?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 12: Go (5 questions)
    (56, 'Explain goroutines and how they differ from traditional threads.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 7, true),
    
    (57, 'Explain channels in Go. What is the difference between buffered and unbuffered channels?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (58, 'How does Go handle memory management and garbage collection? What are common memory leak scenarios?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (59, 'Explain Go interfaces and the concept of implicit implementation. How do empty interfaces work?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (60, 'Your image processing service needs to handle 10,000 images per minute with varying processing times (1-30 seconds each). You need to process them concurrently while preventing resource exhaustion, handling failures gracefully, and shutting down cleanly on SIGTERM. Discuss your approach to implementing a worker pool in Go: how would you size the pool, handle job timeouts, implement graceful shutdown with in-flight job completion, and report errors without losing work?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 13: SQL Databases (5 questions)
    (61, 'Explain the difference between INNER JOIN, LEFT JOIN, RIGHT JOIN, and FULL OUTER JOIN.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 7, true),
    
    (62, 'Explain how database transactions work and the use of COMMIT and ROLLBACK.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (63, 'How would you optimize a slow query? Explain the steps and tools you would use.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (64, 'Explain database indexing strategies: B-tree, Hash, GiST, GIN. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (65, 'Your IoT platform ingests sensor readings from 100,000 devices every 10 seconds, storing timestamps, device IDs, and multiple metric values. Queries need to efficiently retrieve data for specific devices over time ranges, aggregate across all devices for dashboards, and purge data older than 90 days. Discuss your approach to schema design, partitioning strategy, index selection, and data lifecycle management. What are the trade-offs between time-based partitioning vs device-based partitioning?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 14: NoSQL Databases (5 questions)
    (66, 'Compare SQL and NoSQL databases. When would you choose each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 10, true),
    
    (67, 'Explain the CAP theorem and its implications for distributed databases. Provide examples.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (68, 'Explain MongoDB indexing and aggregation pipeline. How do they differ from SQL?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (69, 'How would you design a data model in Cassandra for a messaging application? Explain partition keys and clustering columns.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 20, true),
    
    (70, 'Your e-commerce site handles 50,000 requests per second during flash sales. The product catalog (10,000 products) changes infrequently but inventory levels change constantly. Product pages are slow (500ms) due to database load, and you''re seeing stale inventory causing overselling. Discuss your Redis caching strategy: what data structures would you use for different data types, how would you handle cache invalidation for inventory vs product details, what eviction policy fits this workload, and how would you prevent cache stampedes during sales?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 15: Microservices Architecture (5 questions)
    (71, 'What are microservices? How do they differ from monolithic architecture?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 8, true),
    
    (72, 'Explain service discovery in microservices. Compare client-side and server-side discovery patterns.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (73, 'How would you handle distributed transactions in microservices? Explain the Saga pattern.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (74, 'Explain the API Gateway pattern. What problems does it solve and what are potential drawbacks?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (75, 'Your company is breaking a monolithic e-commerce application into microservices. The monolith currently handles user accounts, product catalog, shopping cart, orders, payments, and inventory in a single database with ACID transactions. Discuss how you would decompose this into services, handle data that spans multiple services (e.g., order creation needs inventory check and payment), choose between synchronous and asynchronous communication for different interactions, and ensure the system remains consistent when services fail.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 16: Message Queues (5 questions)
    (76, 'Explain the difference between message queues and publish-subscribe patterns.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 7, true),
    
    (77, 'Compare RabbitMQ and Apache Kafka. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (78, 'Explain message acknowledgment and delivery guarantees (at-most-once, at-least-once, exactly-once).',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (79, 'How would you handle message ordering in a distributed message queue system?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (80, 'Your application needs to send emails, generate PDF reports, and resize images - all triggered by user actions but too slow for synchronous processing. Some tasks are critical (order confirmations) while others are best-effort (analytics). Tasks occasionally fail due to external service issues. Discuss your approach to building async task processing: how would you prioritize tasks, implement retries with exponential backoff, handle poison messages, ensure critical tasks aren''t lost during deployments, and monitor task health?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 17: Caching Strategies (5 questions)
    (81, 'Explain different caching strategies: cache-aside, read-through, write-through, write-behind.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 10, true),
    
    (82, 'What is cache invalidation? Explain strategies and the challenges involved.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (83, 'Explain cache eviction policies: LRU, LFU, FIFO. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (84, 'How would you implement a distributed cache? Discuss consistency, partitioning, and failure handling.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 20, true),
    
    (85, 'Your video streaming platform serves content globally with varying popularity - some videos get millions of views, most get hundreds. Users expect instant playback start and smooth streaming. Your origin servers are in one region but users are worldwide. Discuss your caching strategy across browser, CDN edge, application tier, and database layers. How would you handle cache warming for predicted viral content, invalidation when videos are updated or removed, and cost optimization for the long tail of less popular content?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 18: API Security (5 questions)
    (86, 'Explain the OAuth 2.0 authorization flow. What are the different grant types?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 12, true),
    
    (87, 'What is JWT (JSON Web Token)? Explain its structure and security considerations.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (88, 'Explain common API security vulnerabilities and how to prevent them (SQL injection, XSS, CSRF, etc.).',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 20, true),
    
    (89, 'How would you implement API key management and rotation for a public API with thousands of clients?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 20, true),
    
    (90, 'Your company has 30 microservices communicating over internal networks. A security audit revealed services accept requests from any internal caller, secrets are passed in plain text, and there''s no logging of service-to-service calls. Discuss your approach to securing this architecture: how would you implement mutual authentication between services, authorize which services can call which endpoints, encrypt traffic, manage and rotate credentials, and maintain audit logs for compliance without impacting latency?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 19: Server-Side Performance (5 questions)
    (91, 'What is the difference between vertical and horizontal scaling? When would you use each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 10, true),
    
    (92, 'Explain connection pooling for databases. Why is it important and how do you configure it?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (93, 'How would you identify and fix N+1 query problems in ORM-based applications?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (94, 'Explain different types of load balancing algorithms and when to use each.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (95, 'Your startup''s API currently handles 1,000 requests per second but you''re planning a product launch expected to drive 100x traffic. Current architecture is a single application server with PostgreSQL. Response times must stay under 200ms at p99. Discuss your scaling strategy: what components would you scale first, how would you identify bottlenecks before they occur, what database scaling approach would you take, where would caching help most, and how would you ensure the system degrades gracefully if traffic exceeds projections?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 20: Backend Testing (5 questions)
    (96, 'Explain the testing pyramid. What are unit, integration, and end-to-end tests?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 10, true),
    
    (97, 'How would you implement mocking in tests? Compare different mocking strategies.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (98, 'Explain test-driven development (TDD). What are the benefits and challenges?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (99, 'How would you test database-dependent code? Discuss different approaches and trade-offs.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (100, 'Your team maintains 15 microservices with frequent deployments. Recent production incidents were caused by: API contract changes breaking consumers, a service that passed all tests but failed under load, and cascading failures when a downstream service was slow. Test coverage is high but confidence in deployments is low. Discuss your testing strategy: how would you implement contract testing to catch integration issues early, introduce chaos engineering to find resilience gaps, and structure test environments to catch issues that unit tests miss?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- ============================================================================
    -- PART 3: Frontend Engineering Topics (Topics 21-35)
    -- ============================================================================

    -- Topic 21: JavaScript (5 questions)
    (101, 'Explain the difference between var, let, and const in JavaScript.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 5, true),
    
    (102, 'Explain JavaScript closures and provide a practical use case.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (103, 'What is the event loop in JavaScript? Explain how async operations work with call stack, callback queue, and microtask queue.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (104, 'Explain prototypal inheritance in JavaScript. How does it differ from classical inheritance?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (105, 'You''re building a utility library and need to understand Promises deeply for async error handling and resource cleanup. Explain the internal mechanics of how a Promise transitions between pending, fulfilled, and rejected states. How does the microtask queue ensure proper chaining order? What happens when you return a Promise from a .then() handler versus returning a plain value? How would error propagation work through a chain of .then() and .catch() calls?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 22: TypeScript (5 questions)
    (106, 'What are the main benefits of using TypeScript over JavaScript?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 6, true),
    
    (107, 'Explain TypeScript generics and provide examples of their use in functions and classes.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (108, 'What are utility types in TypeScript? Explain Partial, Pick, Omit, and Record with examples.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 10, true),
    
    (109, 'Explain the difference between interface and type in TypeScript. When should you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (110, 'Your application has a complex event system where different modules emit and listen to various events (user:login, cart:updated, order:placed, etc.). You want TypeScript to catch errors at compile time when: a listener subscribes to a non-existent event, a listener''s callback has wrong parameter types for that event, or an emitter passes wrong data for an event. Discuss how you would structure the type system using mapped types, conditional types, and generics to achieve full type safety across event names and their payloads.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 23: React (5 questions continuing frontend)
    (111, 'Explain the difference between props and state in React.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 6, true),
    
    (112, 'What is the Virtual DOM? How does React''s reconciliation algorithm work?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (113, 'Explain React hooks lifecycle. How do useEffect cleanup functions work?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 12, true),
    
    (114, 'What are React render props and higher-order components (HOCs)? Compare them with hooks.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 15, true),
    
    (115, 'Your team is building multiple forms across the application with requirements including: async validation against APIs, field dependencies (field B options depend on field A value), multi-step wizards with per-step validation, autosave drafts, and showing validation errors only after field blur or form submission. Existing form libraries feel too heavy or don''t fit your needs. Discuss your approach to creating a reusable form state hook: what state would it manage, how would you handle the validation lifecycle, and how would you make it composable for different form patterns?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 24: Vue.js (5 questions)
    (116, 'What is the Composition API in Vue 3 and how does it differ from Options API? When would you use each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (117, 'Explain reactivity in Vue 3. How do ref() and reactive() differ? What are the gotchas?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (118, 'How would you implement a custom Vue directive for click-outside detection? Include lifecycle hooks and edge cases.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (119, 'Compare Pinia and Vuex. What are the architectural differences and migration considerations?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (120, 'Your company provides a white-label SaaS platform where each tenant has their own branding (colors, logos, fonts), language preferences, and enabled feature sets. The Vue 3 application needs to load tenant configuration at runtime, switch themes without reload, handle tenant-specific routes, and disable UI elements for features the tenant hasn''t purchased. Discuss your approach to architecting this as a Vue plugin: how would you structure the plugin API, manage reactive tenant state, integrate with Vue Router for tenant-specific routes, and handle the initial loading state?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 25: Angular (5 questions)
    (121, 'Explain dependency injection in Angular. How does the hierarchical injector system work?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (122, 'What is Zone.js and how does it enable change detection? What are alternatives in modern Angular?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (123, 'How do you implement lazy loading with preloading strategies in Angular? Design a custom preloading strategy.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (124, 'Explain Angular Signals (v16+). How do they improve upon RxJS for state management?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (125, 'Your organization has 5 teams working on different parts of a large Angular application. Deployments are slow because everyone must coordinate, and a bug in one team''s code blocks others from releasing. You''re evaluating micro-frontends using Module Federation. Discuss the architectural considerations: how would you handle shared dependencies (Angular itself, UI component library) to avoid version conflicts, implement cross-app routing and deep linking, share authentication state and user context between apps, and manage the complexity this approach introduces?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 26: HTML/CSS (5 questions)
    (126, 'What is the CSS box model? Explain box-sizing: border-box vs content-box with practical examples.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (127, 'Explain CSS Grid vs Flexbox. When should you use each? Provide a practical use case for CSS Grid.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (128, 'How do CSS custom properties (variables) enable dynamic theming? Implement a light/dark mode system.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (129, 'What are CSS containment and content-visibility? How do they improve rendering performance?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (130, 'Your team of 10 frontend developers works on a large React application with 500+ components. CSS has become unmaintainable: styles leak between components, specificity wars require !important, and developers are afraid to modify existing styles. The team wants to adopt a scalable CSS architecture. Discuss your approach to organizing CSS using BEM methodology for naming, CSS Modules for scoping, and CSS custom properties for theming. How would you migrate existing styles incrementally and establish conventions that scale?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 27: State Management (5 questions)
    (131, 'When do you need a state management library vs React Context? What are the trade-offs?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (132, 'Explain Redux middleware. How would you implement a custom middleware for API call logging and retry logic?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (133, 'How do you implement optimistic updates with rollback in Redux? Handle concurrent updates and conflicts.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (134, 'Compare Zustand, Jotai, and Recoil. What are architectural differences and when to use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (135, 'Your field service application must work in areas with unreliable connectivity - technicians fill out inspection forms, take photos, and submit reports while potentially offline for hours. Data must not be lost, and when connectivity returns, changes should sync automatically. Conflicts may occur if the same record was modified on the server. Discuss your state management approach: how would you queue offline mutations, handle sync when connectivity returns, resolve conflicts between local and server changes, and provide users visibility into sync status?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 28: Web Performance Optimization (5 questions)
    (136, 'What are Core Web Vitals (LCP, FID, CLS)? How do you measure and optimize them?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (137, 'Explain code splitting strategies in React/Webpack. Implement route-based and component-based code splitting.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (138, 'How do you optimize images for web performance? Compare different formats and loading strategies.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (139, 'What are render-blocking resources? How do you eliminate them using async, defer, and resource hints?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (140, 'Your React analytics dashboard displays 50+ charts and tables with data refreshing every 30 seconds. Users report the page freezes during updates, scrolling is choppy, and initial load takes 8 seconds. Lighthouse shows poor LCP and TBT scores. The dashboard aggregates data from multiple APIs and renders complex visualizations. Discuss your performance optimization strategy: how would you diagnose the specific bottlenecks, implement virtualization for large data sets, optimize re-renders during data updates, and improve perceived performance during initial load?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 29: Browser APIs (5 questions)
    (141, 'Compare localStorage, sessionStorage, and IndexedDB. When should you use each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (142, 'Explain the Fetch API with AbortController. How do you handle timeouts and request cancellation?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (143, 'How does the Intersection Observer API work? Implement infinite scroll and lazy image loading.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (144, 'Explain Web Workers. How do you structure communication for CPU-intensive tasks?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (145, 'Your progressive web app needs to work offline and handle poor network conditions gracefully. Discuss implementing a Service Worker caching strategy covering different approaches for static assets versus API calls, handling cache versioning during deployments, implementing background sync for failed requests, and notifying users when updates are available',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 30: Responsive Design (5 questions)
    (146, 'What is mobile-first design? Compare mobile-first vs desktop-first CSS approaches.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (147, 'Explain CSS Grid vs Flexbox for responsive layouts. When should you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (148, 'How do you handle images responsively? Explain srcset, sizes, and the picture element.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (149, 'What are container queries? How do they differ from media queries and when should you use them?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (150, 'Your team needs to build a responsive dashboard that works across all devices from mobile phones to ultra-wide monitors. Discuss your approach to layout strategy covering mobile-first versus desktop-first decisions, using CSS Grid and Flexbox for different breakpoints, handling the sidebar on mobile devices, implementing fluid typography, and ensuring the layout is maintainable',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 31: Build Tools (5 questions)
    (151, 'What is the difference between Webpack and Vite? When would you choose each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (152, 'Explain tree shaking in JavaScript bundlers. What makes code tree-shakeable?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (153, 'How do you configure multiple environments (dev, staging, production) in a modern build pipeline?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (154, 'What are source maps? Explain different source map types and their trade-offs.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (155, 'Your team''s Webpack build takes 8 minutes locally and 15 minutes in CI, causing developer frustration and slow deployments. The bundle size has grown to 4MB and initial page load is suffering. Discuss your approach to diagnosing build performance bottlenecks, choosing between Webpack optimizations vs migrating to Vite, implementing effective code splitting, and setting up build caching. What trade-offs would you consider between build time and bundle optimization?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 32: Frontend Testing (5 questions)
    (156, 'Compare unit testing, integration testing, and E2E testing in frontend. What should each cover?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (157, 'How do you test React components with React Testing Library? Explain best practices for queries and assertions.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (158, 'Explain API mocking strategies for frontend tests. Compare MSW, jest.mock, and manual mocks.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (159, 'How do you write E2E tests with Playwright? Explain page objects, fixtures, and parallelization.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (160, 'Your React application has grown to 100+ components with OAuth authentication, WebSocket real-time updates, Stripe payment integration, and Google Maps embedding. Test coverage is 20% and bugs frequently reach production. The team wants to improve quality but is unsure where to focus testing effort. Discuss your testing strategy: how would you prioritize what to test first, structure tests for components that depend on auth state, mock real-time connections and third-party services, and set up CI to catch regressions without tests being flaky?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 33: CSS Frameworks (5 questions)
    (161, 'Compare Tailwind CSS, Bootstrap, and Material-UI. When would you choose each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (162, 'How does Tailwind CSS purging/tree-shaking work? Optimize a production build.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (163, 'Explain CSS-in-JS vs traditional CSS. Compare styled-components, Emotion, and CSS Modules.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (164, 'How do you implement a design system with Tailwind CSS? Customize theme and create reusable components.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (165, 'Your company is rebranding and needs to support multiple themes (light/dark modes, plus 3 brand color variations) across 200+ React components using Tailwind CSS. Users should be able to toggle themes instantly, and their preference should persist. Discuss your strategy for organizing CSS variables with Tailwind, handling theme switching without page reload, managing component variants, and ensuring accessibility contrast ratios are maintained across all themes. What are the performance implications?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 34: Web Accessibility (5 questions)
    (166, 'What are WCAG guidelines? Explain the four POUR principles and their importance.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (167, 'How do you implement keyboard navigation in complex components (dropdown, modal, tabs)? Explain focus management.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (168, 'Explain ARIA attributes and when to use them. What are common misuses?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (169, 'How do you ensure proper color contrast and support for color blindness? Explain testing tools and techniques.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (170, 'Your team has built a complex data table component with sorting, filtering, inline editing, and pagination, but accessibility audits show it fails WCAG 2.1 AA compliance. Screen reader users cannot navigate the table effectively, and keyboard-only users struggle with the interactive features. Discuss your approach to retrofitting accessibility: how would you implement proper ARIA roles and live regions, handle focus management during sorting/filtering operations, announce dynamic content changes, and ensure keyboard navigation works for all interactive elements?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 35: UI/UX Principles (5 questions)
    (171, 'Explain the key principles of user-centered design. How do they apply to frontend development?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (172, 'What are loading states and skeleton screens? Implement them effectively in a React application.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (173, 'Explain micro-interactions and their role in UX. Provide examples of effective implementations.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (174, 'How do you design and implement effective error states and recovery mechanisms?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (175, 'Your insurance application has a 15-field quote form that users frequently abandon. Requirements include: conditional fields based on previous answers, real-time premium calculation, address autocomplete, file uploads for documents, saving partial progress, and accessibility compliance for screen readers. Discuss your approach to implementing this form: how would you structure the multi-step flow, handle validation timing (on blur vs on submit vs real-time), implement autosave without overwhelming the server, and ensure the form is accessible and provides clear error recovery guidance?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 36: Linux/Unix (5 questions)
    (176, 'Explain the Linux file system hierarchy. What are the purposes of /etc, /var, /usr, /home, /tmp?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (177, 'How do Linux file permissions work? Explain chmod, chown, and special permissions (setuid, setgid, sticky bit).',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (178, 'Explain process management in Linux. How do you use ps, top, htop, kill, systemctl?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (179, 'How do you debug networking issues in Linux? Explain netstat, ss, tcpdump, curl, dig.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (180, 'Your team''s deployment process currently involves SSHing into servers and running manual commands, leading to inconsistent deployments and occasional downtime. You need to implement automated deployment with bash scripting. Discuss your strategy for implementing atomic deployments with instant rollback capability, health check integration to prevent bad deployments from completing, handling database migrations safely, and notification/alerting on deployment status. What failure scenarios should the script handle?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 37: Shell Scripting (5 questions)
    (181, 'What are the differences between bash, sh, zsh, and fish shells? When would you use each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (182, 'Explain bash scripting best practices: error handling, strict mode, argument parsing, and function design.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (183, 'How do you parse and process text in bash using grep, sed, awk, cut, and regex?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (184, 'Explain process substitution, command substitution, and here documents in bash. Provide practical examples.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (185, 'Your production servers generate 50GB of logs daily across multiple applications. The team needs automated log analysis to detect error spikes, identify recurring patterns, and alert on-call engineers when error rates exceed thresholds. Discuss your strategy using bash tools (grep, awk, sed) for parsing logs efficiently, calculating error statistics without loading entire files into memory, implementing threshold-based alerting, and handling log rotation. What are the limitations of bash for this task vs dedicated log aggregation tools?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 38: Docker Fundamentals (5 questions)
    (186, 'Explain Docker architecture: images, containers, layers, and the differences from VMs.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (187, 'How do you write an optimized Dockerfile? Explain layer caching, multi-stage builds, and security best practices.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (188, 'Explain Docker networking modes (bridge, host, overlay, none). When should you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (189, 'How do you manage data persistence with Docker volumes, bind mounts, and tmpfs? Compare their use cases.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (190, 'Your team is containerizing an existing monolith being split into microservices (API gateway, 3 backend services, PostgreSQL, Redis). The local development environment should mirror production, but developers complain about slow startup times and port conflicts. Discuss your Docker Compose architecture strategy: how would you structure networking between services, handle database initialization and migrations, manage secrets for local development, configure health checks for proper startup ordering, and optimize for fast iteration cycles?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 39: Container Orchestration (5 questions)
    (191, 'What is container orchestration? Compare Docker Swarm, Kubernetes, and when to use each.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (192, 'Explain Kubernetes architecture: control plane, nodes, pods, services. How do they interact?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (193, 'How do you deploy applications to Kubernetes? Explain Deployments, StatefulSets, and DaemonSets.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (194, 'Explain Kubernetes networking: ClusterIP, NodePort, LoadBalancer, Ingress. How do you expose services?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (195, 'You need to deploy a microservice to Kubernetes with zero-downtime deployments, auto-scaling based on CPU/memory, and secret management. Discuss the trade-offs between different update strategies (RollingUpdate vs Recreate vs Blue/Green vs Canary). How would you configure health checks to prevent bad deployments, and what are the considerations for resource requests vs limits?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 40: CI/CD (5 questions)
    (196, 'What is the difference between Continuous Integration, Continuous Delivery, and Continuous Deployment?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (197, 'Explain different deployment strategies: Blue/Green, Canary, Rolling, and Recreate. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (198, 'How would you implement automated testing in a CI/CD pipeline? Discuss the testing pyramid and parallel execution.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (199, 'Explain trunk-based development vs GitFlow. Compare branch strategies and their impact on CI/CD.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (200, 'Your company needs to implement CI/CD for a monorepo containing 20 microservices with different tech stacks (Node.js, Python, Go). Discuss strategies for efficient build caching, selective service deployment based on changes, and managing shared dependencies. What are the trade-offs between monorepo vs multi-repo for CI/CD?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 41: Monitoring and Observability (5 questions)
    (201, 'What is the difference between monitoring, metrics, logging, and tracing? How do they complement each other?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (202, 'Explain the RED and USE methods for monitoring. When would you apply each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (203, 'How do you design effective alerts that minimize false positives and alert fatigue? Explain SLOs and error budgets.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (204, 'Compare pull-based (Prometheus) vs push-based (StatsD, CloudWatch) monitoring. What are the architectural differences and trade-offs?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (205, 'You''re experiencing performance degradation in a distributed microservices system (10+ services). Your monitoring shows increased latency but no clear errors. Describe your debugging approach using observability tools. How would you correlate metrics, logs, and traces to identify the root cause? What signals would you look for?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 42: Logging (5 questions)
    (206, 'What are the differences between structured and unstructured logging? Why is structured logging preferred in modern systems?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (207, 'Explain log levels (DEBUG, INFO, WARN, ERROR, FATAL). When should you use each and how do you manage log verbosity in production?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (208, 'How do you implement log aggregation in a distributed system? Compare ELK stack vs Splunk vs Cloud-native solutions.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (209, 'What is log correlation in distributed systems? How do you implement request tracing across multiple services?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (210, 'Your logging infrastructure is becoming expensive - storing 100TB/month of logs costing $10K/month. Discuss strategies to reduce log volume and costs while maintaining observability. How would you decide what to keep, what to sample, and what to discard? What are the risks?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 43: Infrastructure as Code (5 questions)
    (211, 'What is Infrastructure as Code? Compare declarative vs imperative approaches.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (212, 'Explain Terraform state and why it''s important. How do you manage state in a team environment?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (213, 'Compare Terraform, CloudFormation, Pulumi, and CDK. When would you choose each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (214, 'How do you test Infrastructure as Code? Discuss unit testing, integration testing, and policy validation.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (215, 'You need to migrate existing manually-created infrastructure (100+ resources across AWS: VPCs, EC2, RDS, S3) to Terraform management. Discuss your migration strategy. How do you handle terraform import, minimize risk, and ensure business continuity? What are the challenges of state drift?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 44: Configuration Management (5 questions)
    (216, 'Compare configuration management tools: Ansible, Chef, Puppet, Salt. When would you use each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (217, 'What is configuration drift and how do you prevent/detect it? Discuss immutable vs mutable infrastructure.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (218, 'Explain the concept of desired state configuration. How does it differ from procedural configuration?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (219, 'How do you manage application configuration across multiple environments (dev, staging, production)? Compare different approaches: environment variables, config files, config servers.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (220, 'Your microservices architecture has configuration scattered across environment variables, config files, Kubernetes ConfigMaps, and a legacy database table. Teams are struggling with config sprawl - finding which service uses which config, tracking changes, and ensuring consistency. Design a strategy to consolidate and govern configuration. What are the trade-offs between centralization vs decentralization?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 45: Secrets Management (5 questions)
    (221, 'Why shouldn''t secrets be stored in code or environment variables? What are the risks?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (222, 'Compare cloud-native secrets managers (AWS Secrets Manager, Azure Key Vault, GCP Secret Manager) with HashiCorp Vault. What are the trade-offs?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (223, 'Explain dynamic secrets vs static secrets. How do dynamic secrets improve security?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (224, 'How do you bootstrap secrets in a new application instance? Explain the "chicken and egg" problem and solutions.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (225, 'Your organization has 200+ applications using hundreds of database credentials, API keys, and certificates. Many credentials haven''t been rotated in years and are shared across multiple apps. Design a secrets management migration plan that minimizes risk and business disruption. How do you prioritize which secrets to migrate first? What are the failure modes to plan for?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 46: Service Mesh (5 questions)
    (226, 'What is a service mesh? What problems does it solve in microservices architectures?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (227, 'Compare Istio, Linkerd, and Consul service meshes. When would you choose each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (228, 'Explain how mutual TLS (mTLS) works in a service mesh. What are the benefits over API keys or shared secrets?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (229, 'How does traffic splitting for canary deployments work in a service mesh? Explain request routing and metrics-based rollback.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (230, 'You''re considering adopting a service mesh for your 50-microservice architecture but are concerned about complexity, performance overhead, and operational burden. Discuss the trade-offs. How would you evaluate whether your organization is ready? What incremental adoption strategy would minimize risk?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 47: GitOps (5 questions)
    (231, 'What is GitOps? How does it differ from traditional CI/CD?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (232, 'Compare GitOps tools: ArgoCD vs Flux. What are the key differences?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (233, 'Explain pull-based vs push-based deployment models. What are the security implications of each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (234, 'How do you handle secrets in GitOps when your config is stored in Git? Discuss different approaches.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (235, 'Your team practices GitOps but developers are frustrated by slow deployment times - it takes 5 minutes from Git commit to deployment in the cluster. Your GitOps agent polls Git every 2 minutes and has a 3-minute reconciliation time. How do you reduce this delay? What are the trade-offs between polling interval, webhook triggers, and reconciliation performance?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 48: Disaster Recovery (5 questions)
    (236, 'Define RTO and RPO. How do they drive disaster recovery planning?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (237, 'Describe hot, warm, and cold disaster recovery strategies. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (238, 'What is a disaster recovery drill/test? Why is it important? How often should you run them?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (239, 'How do you handle database disaster recovery? Compare backup/restore, replication, and distributed databases.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (240, 'A major cloud region outage has taken down your primary region. Walk through your disaster recovery response from detection to full recovery. What challenges might you encounter during actual failover that don''t appear in tests? How do you balance speed vs correctness when your business is losing money every minute?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 49: Load Balancing (5 questions)
    (241, 'Explain Layer 4 vs Layer 7 load balancing. What are the trade-offs?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (242, 'Compare load balancing algorithms: round-robin, least connections, least response time, consistent hashing. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (243, 'What is SSL/TLS termination? Should you terminate SSL at the load balancer or at the backend servers?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (244, 'How do you handle session affinity (sticky sessions) in a load-balanced environment? What are the trade-offs?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (245, 'Your application is experiencing uneven load distribution - one backend server consistently receives 3x more traffic than others despite using round-robin load balancing. What could cause this? How would you diagnose and fix it? Discuss both client-side and server-side load balancing considerations.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 50: DevOps Security and Compliance (5 questions)
    (246, 'What is shift-left security? How do you integrate security into the DevOps pipeline?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (247, 'Explain the concept of immutable infrastructure from a security perspective. How does it improve security?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (248, 'How do you implement least privilege access in a DevOps environment where developers need to move fast but security needs to be maintained?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (249, 'What is compliance as code? How do you automate compliance checks for regulations like SOC2, PCI-DSS, HIPAA?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (250, 'Your company needs to achieve SOC2 Type 2 compliance within 6 months, but your infrastructure has grown organically with minimal security controls - no centralized logging, inconsistent MFA adoption, manual access provisioning, secrets in code repositories. Design a compliance roadmap. How do you prioritize efforts? What quick wins can you achieve vs long-term changes? How do you balance compliance work with feature development?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- ============================================================================
    -- DATA ENGINEERING TOPICS (Topics 51-63, Questions 251-315)
    -- ============================================================================

    -- Topic 51: ETL/ELT Pipelines (5 questions)
    (251, 'What is the difference between ETL and ELT? When would you use each approach?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (252, 'Explain idempotency in data pipelines. Why is it important? How do you design idempotent pipelines?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (253, 'How do you handle late-arriving data in data pipelines? Discuss watermarking and window strategies.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (254, 'Compare batch processing vs stream processing. What are the trade-offs? When would you use a Lambda architecture vs Kappa architecture?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (255, 'Your daily ETL pipeline is taking progressively longer to complete - started at 2 hours, now taking 8+ hours and missing SLAs. Data volume has grown 3x, but processing time has grown 4x. The pipeline reads from PostgreSQL source, does transformations in Python pandas, loads to Redshift. How would you diagnose the bottleneck and optimize? Discuss strategies for incremental processing, parallelization, and when to migrate to different technologies.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 52: Data Warehousing (5 questions)
    (256, 'Explain the difference between OLTP and OLAP databases. How do they differ in design and optimization?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (257, 'What is a star schema vs snowflake schema? When would you use each? Discuss fact and dimension tables.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (258, 'Compare cloud data warehouses: Snowflake, BigQuery, and Redshift. What are the key architectural differences and trade-offs?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (259, 'Explain materialized views in data warehousing. How do they differ from regular views? What are refresh strategies and their trade-offs?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (260, 'Your data warehouse queries are slowing down significantly as data grows. A critical dashboard running daily aggregations now takes 45 minutes instead of 5 minutes. The query joins a 500M row fact table with 10 dimension tables and does extensive GROUP BY operations. How would you approach optimization? Discuss partitioning, clustering, distribution keys, aggregation tables, and when to redesign the schema.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 53: Apache Spark (5 questions)
    (261, 'Explain the architecture of Apache Spark. What are drivers, executors, and cluster managers?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (262, 'Compare Spark RDDs, DataFrames, and Datasets. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (263, 'Explain Spark transformations vs actions. What is lazy evaluation and why does it matter?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (264, 'What are Spark shuffles? Why are they expensive? How do you minimize them?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),


    (265, 'Your Spark job processing 10TB of data is running for 6 hours and frequently failing with OutOfMemory errors and data skew issues. One partition has 100x more data than others. The job does multiple groupBy and join operations. How would you diagnose and fix the performance and stability issues? Discuss partitioning strategies, memory management, and skew handling.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 54: Apache Kafka (5 questions)
    (266, 'What is Apache Kafka? Explain the basic concepts: topics, partitions, producers, consumers, and brokers.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (267, 'Explain Kafka consumer groups and partition assignment. What happens when a consumer joins or leaves a group?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (268, 'What are Kafka offset management strategies? Explain auto-commit vs manual commit and their trade-offs.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (269, 'How does Kafka ensure high availability and fault tolerance? Explain replication, ISR, and recovery.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (270, 'Your Kafka-based real-time analytics system is experiencing increasing lag - consumer group is falling behind producers by hours. The topic has 12 partitions and receives 100K messages/sec. Your consumer group has 4 consumers, each taking 50ms to process a message. How do you diagnose the bottleneck and scale to eliminate lag? Discuss parallelism, partition strategy, consumer optimization, and when to add more partitions.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 55: Apache Airflow (5 questions)
    (271, 'What is Apache Airflow? Explain DAGs, tasks, operators, and how Airflow schedules workflows.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (272, 'How do you handle dependencies between tasks in Airflow? Explain different dependency patterns.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),


    (273, 'What are Airflow XComs? How do you pass data between tasks? What are the limitations?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (274, 'How do you implement retries and error handling in Airflow? Discuss task retries, SLAs, and alerting.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (275, 'Your Airflow environment is struggling with 100+ DAGs running daily. The scheduler is lagging, tasks queue up, and DAG parsing takes minutes. How would you diagnose and optimize Airflow performance? Discuss database optimization, scheduler tuning, executor choice, and DAG design best practices.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 56: Data Quality (5 questions)
    (276, 'What is data quality? What are the key dimensions of data quality?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (277, 'How do you implement data quality checks in data pipelines? Discuss validation strategies and tools.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (278, 'What is data profiling? How does it help identify data quality issues?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (279, 'Explain the concept of data lineage. Why is it important for data quality and governance?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (280, 'Your executive dashboard is showing metrics that don''t match similar reports from other teams. Finance reports $10M revenue, your data pipeline shows $8M for the same period. You need to investigate and resolve the discrepancy. Walk through your troubleshooting process. How do you trace the data lineagebackward, identify where the difference occurs, and establish a single source of truth?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 57: Data Modeling (5 questions)
    (281, 'What is the difference between normalization and denormalization? When would you use each in data modeling?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),


    (282, 'Explain dimensional modeling: fact tables and dimension tables. What is a conformed dimension?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (283, 'What is a slowly changing dimension (SCD)? Explain Type 1, Type 2, and Type 3 SCD strategies.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (284, 'Compare Kimball (dimensional modeling) vs Inmon (normalized enterprise warehouse) vs Data Vault methodologies.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (285, 'You''re designing a data warehouse for a global e-commerce company. Sales occur across 50 countries, 10K products, 100M customers, 1B orders. The business needs to analyze sales by customer segment, product category, time, region, and payment method. Design your fact and dimension tables. How do you handle slowly changing dimensions for customer addresses and product categories? What grain do you choose for the fact table? How do you optimize for common query patterns like "sales by category by quarter" vs detailed drill-down to individual orders?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 58: Stream Processing (5 questions)
    (286, 'What is stream processing? How does it differ from batch processing? What are typical use cases?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (287, 'Compare Apache Kafka, Apache Flink, and Spark Streaming for stream processing. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (288, 'What are stateful vs stateless stream processing? Explain windowing, triggers, and watermarks.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (289, 'Explain backpressure in stream processing. What causes it and how do you handle it?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (290, 'Your real-time fraud detection system processes payment transactions through Flink. Recently you''ve observed increasing lag and occasional transaction processing delays exceeding 10 seconds (SLA is 500ms). The stream processes 50K transactions/sec, does stateful pattern matching (sequence of actions per user), and joins with customer profile data. How do you diagnose where the delay occurs and optimize for ultra-low latency?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

-- Topic 59: Data Lake Architecture (5 questions continuing to 295)
-- Topic 60: Data Governance (5 questions continuing to 300)
-- Topic 61: Change Data Capture (5 questions continuing to 305)
-- Topic 62: Data Partitioning (5 questions continuing to 310)
-- Topic 63: Batch vs Stream (5 questions continuing to 315)

    -- Topic 59: Data Lake Architecture (5 questions)
    (291, 'What is a data lake? How does it differ from a data warehouse? When would you use each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (292, 'Explain the concept of a lakehouse. What problems does it solve? Compare Delta Lake, Apache Iceberg, and Apache Hudi.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),


    (293, 'What is the medallion architecture (Bronze, Silver, Gold)? How do you implement it in a data lake?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (294, 'How do you implement data cataloging and metadata management in a data lake?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (295, 'Your data lake has grown to 500TB across 100K datasets in S3, but teams are struggling to find relevant data, data quality issues are common, and there''s no clear ownership. Additionally, compliance requires cataloging PII within 30 days but you have no visibility into what data contains PII. Design a governance and cataloging strategy. How do you implement discovery, ensure data quality, establish ownership, and automate PII detection?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 60: Data Governance (5 questions)
    (296, 'What is data governance? What are the key components of a data governance framework?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (297, 'Explain the concept of data mesh. How does it differ from centralized data platforms?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (298, 'What is GDPR? How does it impact data engineering practices? Discuss right to erasure and data portability.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (299, 'How do you implement data lineage tracking across a complex data pipeline? What tools and techniques can be used?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (300, 'You need to implement GDPR "right to erasure" across your data ecosystem which includes PostgreSQL (user profiles), MongoDB (user activity logs), S3 data lake (event logs in Parquet), Snowflake warehouse (analytics tables), and ElasticSearch (search indexes). A user requests deletion. Walk through the technical implementation. What are the challenges with backups, logs, and analytics data? How do you ensure complete erasure while maintaining referential integrity?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 61: Change Data Capture (CDC) (5 questions)
    (301, 'What is Change Data Capture (CDC)? Why is it useful? Compare log-based CDC vs query-based CDC.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (302, 'Explain the challenges of implementing CDC from a production database. How do you minimize performance impact?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),


    (303, 'How do you handle schema evolution in CDC pipelines? What happens when source table schema changes?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (304, 'What are the different CDC patterns for syncing data to a data warehouse? Compare snapshot + incremental vs streaming.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (305, 'Your e-commerce platform needs real-time inventory sync from PostgreSQL to Snowflake for analytics. Inventory updates happen 1000/sec during peak. Design a CDC solution. How do you ensure exactly-once semantics, handle backpressure, and maintain low latency (<30sec from DB update to Snowflake)?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 62: Data Partitioning Strategies (5 questions)
    (306, 'What is data partitioning? Why is it important in distributed systems and data warehouses?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (307, 'Compare partition pruning vs full table scan. How do databases optimize partition pruning?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (308, 'What is data skew in partitioning? How does it impact performance and how do you detect and fix it?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (309, 'Explain partition exchange vs partition rebuild. When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (310, 'You have a 50TB events table in Snowflake partitioned by date (daily partitions). Queries filtering by user_id are slow because user_id is not the partition key, resulting in full table scans across all date partitions. How would you optimize for both date and user_id queries without duplicating data?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 63: Real-time vs Batch Processing (5 questions)
    (311, 'What are the key differences between batch and stream processing? When would you choose one over the other?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (312, 'Explain micro-batching in Spark Streaming. How does it differ from true streaming in Flink?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (313, 'What is event time vs processing time? Why does it matter and how do you handle late-arriving events?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (314, 'How do you achieve exactly-once semantics in stream processing? Explain the challenges and solutions.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (315, 'Your company wants to move from nightly batch processing to real-time analytics. Current batch job processes 500GB daily (customer clickstream) with complex joins and aggregations, taking 3 hours to complete. Business wants insights available within 5 minutes of events occurring. Design a migration strategy. What are the risks and how do you minimize them? How do you handle the transition period where both systems run in parallel?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

-- End of Data Engineering section (Topics 51-63, Questions 251-315)


-- ============================================================================
-- MOBILE DEVELOPMENT TOPICS (Topics 64-75, Questions 316-375)
-- ============================================================================

    -- Topic 64: iOS Development (5 questions)
    (316, 'What is the difference between frame and bounds in UIView? When would you use each?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (317, 'Explain the iOS app lifecycle. What happens in each state transition?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (318, 'What is the difference between strong, weak, and unowned references in Swift? How do you prevent retain cycles?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (319, 'Explain the iOS Grand Central Dispatch (GCD). How do you use dispatch queues for concurrency?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (320, 'Your iOS app is experiencing frequent crashes and memory warnings, especially when users navigate deeply through photo galleries (100+ images). Memory usage grows from 100MB to 800MB before the app is terminated. How would you diagnose memory issues and optimize memory usage? Discuss image caching strategies, ARC, and memory profiling.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 65: Android Development (5 questions)
    (321, 'Explain the Android activity lifecycle. What methods are called during configuration changes like screen rotation?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (322, 'What is the difference between Service, IntentService, and JobScheduler in Android? When would you use each?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (323, 'Explain Android memory leaks. How do you prevent leaks with Activities, Context, and static references?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (324, 'What is Jetpack Compose? How does it differ from traditional Android View system? Explain state management in Compose.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),

    
    (325, 'Your Android app shows an ANR (Application Not Responding) dialog when users submit a large form with image uploads. The main thread is blocked for 8-10 seconds during submission. How would you diagnose the ANR and refactor the code to maintain responsiveness? Discuss threading, coroutines, and background execution strategies.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 66: React Native (5 questions)
    (326, 'What is the bridge in React Native? How does JavaScript communicate with native code?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (327, 'Explain React Native FlatList optimization. How do you prevent performance issues with large lists?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (328, 'How do you handle navigation in React Native? Compare React Navigation and React Native Navigation.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (329, 'What are the differences between React Native and developing separate native apps? What are the trade-offs?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (330, 'Your React Native app''s JavaScript bundle size has grown to 8MB, causing slow initial load times (10+ seconds on 3G networks). Users also complaint about occasional crashes on older Android devices (4GB RAM). How would you optimize bundle size, improve load times, and reduce memory footprint? Discuss code splitting, lazy loading, and performance profiling.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 67: Flutter (5 questions)
    (331, 'What is the difference between StatefulWidget and StatelessWidget in Flutter?',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (332, 'Explain Flutter''s declarative UI approach. How does it differ from imperative UI frameworks?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (333, 'What are Flutter providers and state management? Compare Provider, Riverpod, and Bloc patterns.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),

    (334, 'How does Flutter achieve 60fps performance? Explain the rendering pipeline and frame budget.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (335, 'Your Flutter app experiences severe frame drops (10-15fps) when scrolling through a feed with images, complex cards, and animations. Users report the app feels laggy and unresponsive. How would you diagnose the performance issues and optimize rendering? Discuss Flutter DevTools, rendering pipeline, and widget optimization strategies.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 68: Mobile Architecture (5 questions)
    (336, 'What is the MVC pattern in mobile development? How does it compare to MVVM and MVP?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),

    
    (337, 'What is Clean Architecture for mobile apps? Explain the dependency rule and layers.',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (338, 'Explain modular architecture in mobile apps. How do you structure a large app into modules?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (339, 'What is Dependency Injection in mobile development? Compare different DI approaches (manual, Syringe,  Hilt, Koin).',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (340, 'Your mobile app has grown to 100K+ lines of code with 15 developers working simultaneously. Build times have increased to 20+ minutes for full builds, and teams frequently face merge conflicts in shared files. Module boundaries are unclear, leading to tangled dependencies. How would you restructure the app architecture to improve build times, enable parallel development, and enforce modularity? Discuss modularization strategies, dependency management, and tooling.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 69: Mobile Security (5 questions)
    (341, 'What is SSL pinning in mobile apps? How does it protect against man-in-the-middle attacks?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),


    (342, 'How do you securely store sensitive data like tokens and passwords in mobile apps?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (343, 'What are common mobile app security vulnerabilities? How do you prevent them?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (344, 'Explain mobile app code obfuscation. What are the trade-offs?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (345, 'Your mobile banking app needs to meet strict security compliance (PCI-DSS for payments, SOC 2). Security audit found several vulnerabilities: tokens stored in SharedPreferences/UserDefaults (unencrypted), API calls over HTTP in legacy modules, no root/jailbreak detection, hardcoded API keys in source code, and screenshots enabled on sensitive screens. How would you systematically remediate these vulnerabilities while maintaining app functionality? Discuss secure storage, network security, anti-tampering, and compliance validation.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 70: Mobile Performance (5 questions)
    (346, 'What causes app startup time to be slow? How do you optimize cold start performance?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (347, 'How do you detect and fix memory leaks in mobile apps?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (348, 'What is the difference between bitmap pooling and caching? How do you optimize image memory usage?',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (349, 'Explain Android App Bundles and how they reduce APK size.',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (350, 'Your mobile e-commerce app is experiencing poor performance: product listing scrolls at 30fps (target 60fps), image loading causes UI freezes, search takes 3-5 seconds to return results, and the app consumes 400MB of memory (leaking over time). Users complain about battery drain and crashes on older devices. How would you systematically diagnose and optimize performance across rendering, memory, network, and battery? Discuss profiling tools, optimization techniques, and performance monitoring.',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 71: Push Notifications (5 questions)
    (351, 'How do push notifications work in mobile apps and what are the differences between FCM for Android and APNs for iOS',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (352, 'Explain the process of implementing push notification handlers in mobile applications for both foreground and background states',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (353, 'How do you handle push notification token management and refresh scenarios across app reinstalls and device changes',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (354, 'What are rich push notifications and how do you implement custom actions and media attachments',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (355, 'Your messaging app with 10 million users needs to send targeted notifications based on user preferences (muted conversations, do-not-disturb schedules, notification categories). Users report missing notifications, delayed delivery, and notifications for muted chats. You need to handle token refresh when users reinstall the app and gracefully degrade when FCM/APNs have outages. Discuss your approach to notification targeting, token lifecycle management, delivery tracking, and handling platform-specific quirks. How would you debug why a specific user isn''t receiving notifications?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 72: Mobile Security (5 questions)
    (356, 'What are the key mobile app security concerns and how do you protect against common vulnerabilities',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (357, 'Explain certificate pinning in mobile applications and discuss the trade-offs between security and flexibility',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (358, 'How do you securely store sensitive data like authentication tokens and encryption keys in mobile apps',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (359, 'What is reverse engineering of mobile apps and what techniques can you use to make it harder',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (360, 'Your mobile banking app handles sensitive transactions and has been targeted by fraudsters using stolen credentials, session hijacking, and man-in-the-middle attacks. Users also complain about too many security prompts degrading UX. Discuss your authentication strategy: how would you implement biometric authentication with fallback options, manage token refresh and session timeouts, detect and respond to rooted/jailbroken devices, protect against common attack vectors while minimizing friction for legitimate users? What security vs UX trade-offs would you make?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 73: Mobile Testing (5 questions)
    (361, 'Compare unit testing, integration testing, and UI testing for mobile applications. What frameworks do you use for each',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (362, 'How do you implement end-to-end testing for mobile apps across multiple devices and OS versions',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (363, 'Explain snapshot testing for mobile UI and how it helps catch unintended visual changes',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (364, 'What strategies do you use for testing mobile apps with different network conditions and offline scenarios',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (365, 'Your mobile app has grown to 50 screens with complex user flows and your manual testing is taking 2 days per release. Design an automated testing strategy that covers critical paths while being maintainable. How do you handle device fragmentation and flaky tests',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 74: Mobile CI/CD (5 questions)
    (366, 'What are the key components of a mobile CI/CD pipeline and how do they differ from web application pipelines',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (367, 'Explain the mobile app signing and provisioning process for iOS and Android in CI/CD',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (368, 'How do you implement automated app distribution to testers and staged rollouts to production',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (369, 'What techniques do you use to reduce mobile app build times in CI/CD pipelines',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (370, 'Your company ships iOS and Android apps weekly, but releases are painful: iOS builds take 45 minutes, Android builds fail intermittently, code signing issues block releases, and coordinating beta testing across platforms is manual. You need separate builds for dev, staging, and production with different API endpoints and feature flags. Discuss your CI/CD pipeline architecture: how would you structure the pipeline for both platforms, manage signing certificates and provisioning profiles securely, implement staged rollouts with automatic rollback, and reduce the build-test-deploy cycle time?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),


    -- Topic 75: Mobile Analytics (5 questions)
    (371, 'What mobile analytics metrics are most important to track and how do you implement analytics without impacting performance',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (372, 'Explain crash reporting and symbolication in mobile apps. How do you debug production crashes',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (373, 'How do you implement A/B testing in mobile applications and what are the challenges compared to web',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (374, 'What techniques do you use for session recording and user behavior analytics while respecting privacy',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (375, 'Your product team wants detailed analytics on user behavior but you need to minimize battery drain, network usage, and respect privacy regulations like GDPR. Design an analytics architecture that balances these concerns. How do you handle offline events and ensure data accuracy',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- ============================================================================
    -- MACHINE LEARNING TOPICS (Topics 76-90, Questions 376-450)
    -- ============================================================================

    -- Topic 76: ML Fundamentals (5 questions)
    (376, 'Explain the difference between supervised, unsupervised, and reinforcement learning with examples',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (377, 'What is overfitting and underfitting in machine learning and how do you detect and prevent them',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (378, 'Explain the bias-variance tradeoff and how it impacts model performance',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (379, 'Compare classification and regression tasks. What evaluation metrics do you use for each',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (380, 'You are building a fraud detection model for credit card transactions. Walk through your approach from problem formulation to model selection, handling class imbalance, choosing evaluation metrics, and deciding on precision-recall tradeoffs',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 77: Feature Engineering (5 questions)
    (381, 'What is feature engineering and why is it important in machine learning pipelines',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (382, 'Explain different techniques for handling missing data in datasets',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (383, 'How do you encode categorical variables and when would you use one-hot encoding vs label encoding vs embeddings',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (384, 'What is feature scaling and normalization and when is it necessary for machine learning models',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (385, 'You have a dataset with 1000 features for predicting customer churn but many features are correlated and some have missing values. Design a feature engineering pipeline covering missing value imputation, feature selection, dimensionality reduction, and creating new features. How do you avoid data leakage',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 78: Model Training (5 questions)
    (386, 'Explain the training, validation, and test set split. Why do you need all three',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (387, 'What is cross-validation and when would you use k-fold vs stratified k-fold vs time series split',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (388, 'How do you tune hyperparameters and compare grid search, random search, and Bayesian optimization',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (389, 'Explain regularization techniques like L1, L2, and dropout. When would you use each',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (390, 'Your model training is taking 12 hours per experiment making iteration slow. The dataset has 10 million records and you are trying various algorithms and hyperparameters. Design a strategy to speed up experimentation while maintaining model quality. Consider sampling, distributed training, early stopping, and caching',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 79: Deep Learning (5 questions)
    (391, 'Explain the basic architecture of a neural network including layers, activations, and backpropagation',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (392, 'Compare different optimization algorithms like SGD, Adam, RMSprop and when to use each',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (393, 'What is transfer learning and how do you fine-tune pre-trained models for new tasks',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (394, 'Explain batch normalization and layer normalization. Why do they help training',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (395, 'You need to train a deep learning model for image classification but have limited labeled data and computation resources. Discuss strategies including transfer learning, data augmentation, model architecture choices, and training techniques to achieve good performance with constraints',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 80: Computer Vision (5 questions)
    (396, 'What are convolutional neural networks and why are they effective for image processing',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (397, 'Explain common computer vision tasks like image classification, object detection, and semantic segmentation',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (398, 'Compare popular CNN architectures like ResNet, VGG, and EfficientNet',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (399, 'How do you handle data augmentation for computer vision tasks and what transformations are commonly used',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (400, 'Your client wants to deploy object detection on security cameras to identify people and vehicles entering a facility. The system must run on edge devices (limited GPU), achieve under 100ms latency for real-time alerting, work across day/night conditions, and minimize false positives (staff have alarm fatigue from current system). Discuss your approach: how would you select and optimize a model for edge deployment, handle varying lighting and weather conditions, tune the confidence threshold trade-off between missed detections and false alarms, and evaluate system performance in production?',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 81: Natural Language Processing (5 questions)
    (401, 'What is tokenization in NLP and how do different tokenization strategies like word-level, subword (BPE), and character-level affect model performance',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (402, 'Explain word embeddings like Word2Vec and GloVe. How do they capture semantic relationships between words',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (403, 'Compare RNN, LSTM, and Transformer architectures for sequence modeling tasks',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (404, 'What is attention mechanism and why was it a breakthrough in NLP',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (405, 'You need to build a sentiment analysis system for customer reviews in multiple languages with limited labeled data per language. Discuss approaches including transfer learning from multilingual models, data augmentation strategies, and handling class imbalance between positive and negative reviews',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 82: Recommender Systems (5 questions)
    (406, 'Explain the difference between collaborative filtering and content-based filtering in recommender systems',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (407, 'What is the cold start problem in recommendation systems and how do you address it',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (408, 'Compare matrix factorization techniques like SVD and ALS for collaborative filtering',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (409, 'Explain how neural collaborative filtering and deep learning improve traditional recommendation approaches',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (410, 'Your e-commerce platform needs to recommend products to 100 million users with real-time updates as user behavior changes. Discuss the trade-offs between accuracy and scalability, handling sparse user-item interactions, incorporating contextual information like time and location, and measuring recommendation quality beyond accuracy',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 83: Time Series Forecasting (5 questions)
    (411, 'What makes time series data different from regular tabular data in machine learning',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (412, 'Explain stationarity in time series and why it matters for forecasting models',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (413, 'Compare ARIMA, Prophet, and LSTM approaches for time series forecasting',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (414, 'How do you handle seasonality and trends in time series forecasting',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (415, 'You need to forecast demand for 10,000 products across 500 stores with varying seasonal patterns and promotional events. Discuss strategies for handling the scale, incorporating external factors like holidays and weather, dealing with intermittent demand for slow-moving products, and providing uncertainty estimates with predictions',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 84: MLOps (5 questions)
    (416, 'What is MLOps and how does it differ from traditional DevOps',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (417, 'Explain the ML lifecycle from experimentation to production deployment',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (418, 'What is model versioning and why is it important in machine learning systems',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (419, 'Compare different model serving strategies like batch prediction, real-time API, and edge deployment',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (420, 'Your ML team is struggling with inconsistent results between training and production, slow deployment cycles taking weeks, and difficulty tracking which model version is running where. Design an MLOps architecture covering experiment tracking, model registry, CI/CD pipelines, and deployment strategies that enables rapid iteration while maintaining reproducibility',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 85: Model Deployment (5 questions)
    (421, 'What are the main challenges in deploying machine learning models to production',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (422, 'Explain the difference between online and offline model serving',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (423, 'How do you handle model updates in production without downtime using strategies like blue-green deployment or canary releases',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (424, 'What is feature store and why is it important for ML model deployment',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (425, 'Your computer vision model takes 500ms to process each image but you need to serve predictions with less than 100ms latency at 1000 requests per second. Discuss optimization strategies including model compression, quantization, hardware acceleration, batching, and caching while maintaining acceptable accuracy',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 86: Model Monitoring (5 questions)
    (426, 'Why is model monitoring important after deployment and what can go wrong with production ML models',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (427, 'Explain data drift and model drift. How do they impact model performance',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (428, 'What metrics should you monitor for a classification model in production',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (429, 'How do you detect concept drift and trigger model retraining automatically',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (430, 'Your fraud detection model was performing well but accuracy has dropped from 95% to 78% over three months without any code changes. Walk through your debugging approach covering data quality checks, drift detection, performance analysis across different segments, and determining whether to retrain or investigate data issues',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 87: Experiment Tracking (5 questions)
    (431, 'What is experiment tracking in machine learning and why is it important',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (432, 'Explain what metadata you should track for each ML experiment',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (433, 'Compare different experiment tracking tools like MLflow, Weights and Biases, and Neptune',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (434, 'How do you organize and compare hundreds of experiments to identify the best performing model',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (435, 'Your data science team of 20 people is running 100+ experiments per week with different datasets, features, and algorithms but struggling to reproduce results or know what has been tried before. Design an experiment tracking strategy covering what to log, how to organize experiments, comparing results, and ensuring reproducibility',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 88: AutoML (5 questions)
    (436, 'What is AutoML and what parts of the machine learning pipeline can it automate',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (437, 'Explain neural architecture search and how it differs from traditional hyperparameter tuning',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (438, 'Compare different AutoML approaches like Google AutoML, H2O.ai, and Auto-sklearn',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (439, 'What are the limitations and trade-offs of using AutoML versus manual model development',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (440, 'You need to build ML models for 50 different business use cases with limited data science resources. Discuss when AutoML is appropriate versus manual development, how to balance automation with domain expertise, handling edge cases AutoML might miss, and ensuring model interpretability and compliance',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 89: Explainable AI (5 questions)
    (441, 'Why is model interpretability important especially in regulated industries like healthcare and finance',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (442, 'Explain the difference between model-agnostic and model-specific interpretability methods',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (443, 'Compare LIME, SHAP, and feature importance for explaining model predictions',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (444, 'What is the trade-off between model accuracy and interpretability',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (445, 'Your bank is using a deep learning model for loan approval but regulators require you to explain why each application was rejected. Discuss strategies for making complex models explainable, balancing accuracy with interpretability, communicating explanations to non-technical stakeholders, and handling bias and fairness concerns',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 90: ML Ethics and Fairness (5 questions)
    (446, 'What are common sources of bias in machine learning systems',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (447, 'Explain different fairness metrics like demographic parity, equal opportunity, and equalized odds',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (448, 'How do you detect and measure bias in training data and model predictions',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (449, 'What techniques can you use to mitigate bias in machine learning models',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (450, 'Your hiring algorithm is showing significantly lower acceptance rates for certain demographic groups despite using only job-relevant features. Walk through how you would investigate this fairness issue, identify root causes, evaluate different fairness metrics and their trade-offs, and determine what interventions would be appropriate while maintaining predictive performance',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- ============================================================================
    -- SYSTEM DESIGN TOPICS (Topics 91-100, Questions 451-500)
    -- ============================================================================

    -- Topic 91: System Design Fundamentals (5 questions)
    (451, 'What are the key considerations when designing a scalable distributed system',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (452, 'Explain the CAP theorem and its implications for distributed database design',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (453, 'Compare vertical scaling versus horizontal scaling with their trade-offs',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (454, 'What is the difference between stateful and stateless services and when would you use each',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (455, 'You are tasked with redesigning a monolithic e-commerce application that is struggling with Black Friday traffic spikes and slow deployment cycles. Discuss your approach to identifying bottlenecks, deciding what to extract first, handling data consistency during migration, and ensuring zero downtime during the transition',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 92: Scalability Patterns (5 questions)
    (456, 'What is database sharding and when should you consider it',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (457, 'Explain different caching strategies like write-through, write-back, and cache-aside',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (458, 'Compare database read replicas versus caching for improving read performance',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (459, 'What is the circuit breaker pattern and how does it improve system resilience',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (460, 'Your social media application has grown from 100K to 10M users and the database is becoming a bottleneck with slow queries and frequent timeouts. Discuss strategies for scaling including read replicas, caching layers, database sharding approaches, query optimization, and handling eventual consistency',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 93: Database Design Patterns (5 questions)
    (461, 'What are the trade-offs between SQL and NoSQL databases',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (462, 'Explain database normalization and when denormalization might be beneficial',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (463, 'Compare different NoSQL database types: key-value, document, column-family, and graph databases',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (464, 'What is eventual consistency and when is it acceptable versus requiring strong consistency',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (465, 'Design the database architecture for a global ride-sharing application that needs to handle millions of concurrent ride requests, track driver locations in real-time, calculate pricing dynamically, and maintain ride history. Discuss partitioning strategies, consistency requirements, handling hot spots, and geo-distributed data placement',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 94: Caching Strategies (5 questions)
    (466, 'What problems does caching solve and what are common cache invalidation strategies',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (467, 'Explain the differences between CDN, application-level cache, and database query cache',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (468, 'Compare Redis and Memcached for caching use cases',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (469, 'What is cache stampede and how do you prevent it',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (470, 'Your news website is experiencing severe load on the database during breaking news events when millions of users request the same article simultaneously. Design a multi-layer caching strategy covering CDN, application cache, and database cache, handling cache invalidation when articles are updated, and preventing thundering herd problems',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 95: Load Balancing (5 questions)
    (471, 'What is load balancing and why is it necessary in distributed systems',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (472, 'Compare different load balancing algorithms like round-robin, least connections, and weighted distribution',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (473, 'Explain Layer 4 versus Layer 7 load balancing and when to use each',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (474, 'How do load balancers perform health checks and handle unhealthy instances',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (475, 'Design a load balancing strategy for a video streaming platform with geographically distributed users, varying content popularity, and live streaming requirements. Discuss global versus regional load balancing, session affinity considerations, handling server failures gracefully, and optimizing for video quality of service',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 96: Microservices Architecture (5 questions)
    (476, 'What are microservices and how do they differ from monolithic architecture',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (477, 'Explain service discovery and why it is important in microservices',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (478, 'Compare different communication patterns in microservices: synchronous HTTP, asynchronous messaging, and event-driven',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (479, 'What is the saga pattern for managing distributed transactions across microservices',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (480, 'Your company is migrating from a monolith to microservices and experiencing challenges with inter-service communication failures, data consistency across services, and increased operational complexity. Discuss strategies for service boundaries, handling failures with circuit breakers and retries, managing distributed transactions, and monitoring service dependencies',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 97: API Design (5 questions)
    (481, 'What are REST API design best practices and common HTTP status codes',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (482, 'Compare REST, GraphQL, and gRPC for API design',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (483, 'Explain API versioning strategies and their trade-offs',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (484, 'How do you design APIs for rate limiting and preventing abuse',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (485, 'Design a public API for a payment processing platform that needs to support high throughput, maintain backward compatibility, provide clear error messages, implement security best practices, and handle rate limiting. Discuss authentication approaches, idempotency for payment operations, webhook design for async notifications, and API documentation strategy',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 98: Message Queues (5 questions)
    (486, 'What problems do message queues solve in distributed systems',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (487, 'Explain the difference between message queues and publish-subscribe patterns',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (488, 'Compare RabbitMQ, Apache Kafka, and Amazon SQS',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (489, 'What are dead letter queues and when should you use them',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (490, 'Your order processing system needs to handle 10,000 orders per second during flash sales while ensuring orders are processed exactly once and in the correct sequence. Design a message queue architecture discussing choice of queue technology, handling backpressure, ensuring message ordering, implementing retry logic with exponential backoff, and monitoring queue health',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 99: Distributed Systems (5 questions)
    (491, 'What is consensus in distributed systems and why is it challenging',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (492, 'Explain leader election and common algorithms like Raft or Paxos at a high level',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (493, 'What is the split-brain problem in distributed systems and how do you prevent it',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (494, 'Compare different replication strategies: master-slave, master-master, and quorum-based',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (495, 'Design a distributed configuration management system similar to etcd or ZooKeeper that needs to provide strong consistency guarantees, handle network partitions gracefully, support automatic failover, and scale to thousands of clients. Discuss consensus algorithms, replication strategies, handling failures, and performance considerations',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 100: Real-time Systems (5 questions)
    (496, 'What are the challenges of building real-time systems compared to batch processing systems',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (497, 'Explain WebSockets and Server-Sent Events for real-time communication',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (498, 'Compare different real-time data processing frameworks like Apache Flink, Spark Streaming, and Kafka Streams',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (499, 'What is backpressure in stream processing and how do you handle it',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (500, 'Design a real-time analytics dashboard for a trading platform that needs to display live market data, calculate moving averages and alerts with sub-second latency, handle millions of events per second, and provide historical playback capability. Discuss stream processing architecture, state management, handling late-arriving data, and ensuring exactly-once processing',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- ============================================================================
    -- ADDITIONAL TOPICS (Topics 101-103, Questions 501-515)
    -- ============================================================================

    -- Topic 101: Security Architecture (5 questions)
    (501, 'What are the OWASP Top 10 security vulnerabilities and how do you prevent them',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (502, 'Explain different authentication mechanisms: session-based, token-based, and OAuth',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (503, 'Compare symmetric and asymmetric encryption and when to use each',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (504, 'What is zero-trust security architecture and how does it differ from perimeter-based security',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (505, 'Your financial services application needs to achieve SOC 2 and PCI DSS compliance while maintaining developer productivity. Discuss security architecture covering authentication and authorization, data encryption at rest and in transit, secrets management, audit logging, vulnerability scanning, and balancing security with usability',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 102: Cloud Architecture (5 questions)
    (506, 'What are the main differences between IaaS, PaaS, and SaaS cloud service models',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (507, 'Explain the benefits and challenges of multi-cloud versus single-cloud strategy',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (508, 'Compare serverless computing with traditional container-based deployments',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (509, 'What is cloud cost optimization and what strategies can reduce cloud spending',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (510, 'Your startup is experiencing unpredictable growth and current infrastructure costs are consuming 40% of revenue with frequent outages during traffic spikes. Design a cloud architecture strategy discussing right-sizing resources, auto-scaling policies, choosing between serverless and containers, implementing disaster recovery, and optimizing costs while maintaining performance SLAs',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true),

    -- Topic 103: Performance Optimization (5 questions)
    (511, 'What are common performance bottlenecks in web applications and how do you identify them',
     NULL, 'technical', 'easy', 'organization', 1, 'custom', 3, true),
    
    (512, 'Explain different profiling techniques for identifying CPU and memory issues',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (513, 'Compare different approaches to database query optimization',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (514, 'What is the difference between latency and throughput and how do you optimize for each',
     NULL, 'technical', 'medium', 'organization', 1, 'custom', 5, true),
    
    (515, 'Your web application API response times have degraded from 100ms to 2 seconds over six months as user base grew from 10K to 1M users. Walk through your systematic approach to diagnosing performance issues covering profiling tools, database query analysis, identifying N+1 queries, evaluating caching opportunities, and determining whether the solution requires code optimization or infrastructure scaling',
     NULL, 'technical', 'hard', 'organization', 1, 'custom', 7, true);
