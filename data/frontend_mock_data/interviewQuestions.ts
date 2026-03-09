import type { Question } from '@/types/interview';

// Self introduction question
export const selfIntroQuestion: Question = {
  id: 'intro-001',
  type: 'open-ended',
  content: "Hello! Welcome to your interview today. Please take a moment to introduce yourself. Tell me about your background, your experience, and what interests you about this role.",
  difficulty: 'easy',
  topic: 'Introduction',
  timeLimit: 120
};

// Domain-related technical questions (non-coding)
export const technicalQuestions: Record<string, Question[]> = {
  dsa: [
    {
      id: 'tech-dsa-001',
      type: 'open-ended',
      content: "Can you explain the difference between a Stack and a Queue? When would you choose one over the other in a real-world application?",
      difficulty: 'easy',
      topic: 'Data Structures',
      timeLimit: 90
    },
    {
      id: 'tech-dsa-002',
      type: 'open-ended',
      content: "What is a Hash Table and how does it handle collisions? Can you describe at least two collision resolution techniques?",
      difficulty: 'medium',
      topic: 'Hash Tables',
      timeLimit: 120
    },
    {
      id: 'tech-dsa-003',
      type: 'open-ended',
      content: "Explain the concept of Binary Search Tree. What are its advantages and what happens when it becomes unbalanced?",
      difficulty: 'medium',
      topic: 'Trees',
      timeLimit: 120
    }
  ],
  'system-design': [
    {
      id: 'tech-sd-001',
      type: 'open-ended',
      content: "What is the difference between horizontal and vertical scaling? When would you prefer one over the other?",
      difficulty: 'medium',
      topic: 'Scalability',
      timeLimit: 120
    },
    {
      id: 'tech-sd-002',
      type: 'open-ended',
      content: "Can you explain what a load balancer does and describe different load balancing algorithms you know?",
      difficulty: 'medium',
      topic: 'Load Balancing',
      timeLimit: 120
    },
    {
      id: 'tech-sd-003',
      type: 'open-ended',
      content: "What is caching and why is it important in system design? Can you describe different caching strategies?",
      difficulty: 'medium',
      topic: 'Caching',
      timeLimit: 120
    }
  ],
  backend: [
    {
      id: 'tech-be-001',
      type: 'open-ended',
      content: "What are RESTful APIs and what are the main HTTP methods used in REST? Can you explain when to use each?",
      difficulty: 'easy',
      topic: 'REST APIs',
      timeLimit: 90
    },
    {
      id: 'tech-be-002',
      type: 'open-ended',
      content: "Explain the difference between SQL and NoSQL databases. When would you choose one over the other?",
      difficulty: 'medium',
      topic: 'Databases',
      timeLimit: 120
    },
    {
      id: 'tech-be-003',
      type: 'open-ended',
      content: "What is authentication versus authorization? Can you describe JWT tokens and how they work?",
      difficulty: 'medium',
      topic: 'Security',
      timeLimit: 120
    }
  ],
  frontend: [
    {
      id: 'tech-fe-001',
      type: 'open-ended',
      content: "Can you explain the Virtual DOM in React and why it improves performance?",
      difficulty: 'medium',
      topic: 'React',
      timeLimit: 120
    },
    {
      id: 'tech-fe-002',
      type: 'open-ended',
      content: "What is the difference between props and state in React? When would you use each?",
      difficulty: 'easy',
      topic: 'React Fundamentals',
      timeLimit: 90
    },
    {
      id: 'tech-fe-003',
      type: 'open-ended',
      content: "Explain CSS Flexbox and Grid. When would you choose one layout system over the other?",
      difficulty: 'medium',
      topic: 'CSS',
      timeLimit: 120
    }
  ],
  behavioral: [
    {
      id: 'tech-beh-001',
      type: 'open-ended',
      content: "Tell me about a challenging project you worked on. What obstacles did you face and how did you overcome them?",
      difficulty: 'medium',
      topic: 'Problem Solving',
      timeLimit: 180
    },
    {
      id: 'tech-beh-002',
      type: 'open-ended',
      content: "Describe a situation where you had a conflict with a team member. How did you handle it?",
      difficulty: 'medium',
      topic: 'Teamwork',
      timeLimit: 180
    },
    {
      id: 'tech-beh-003',
      type: 'open-ended',
      content: "Tell me about a time when you had to learn a new technology quickly. How did you approach it?",
      difficulty: 'easy',
      topic: 'Learning',
      timeLimit: 150
    }
  ],
  devops: [
    {
      id: 'tech-do-001',
      type: 'open-ended',
      content: "What is Docker and how does containerization differ from traditional virtualization?",
      difficulty: 'medium',
      topic: 'Containers',
      timeLimit: 120
    },
    {
      id: 'tech-do-002',
      type: 'open-ended',
      content: "Explain CI/CD pipelines. What are the key stages and why is automation important?",
      difficulty: 'medium',
      topic: 'CI/CD',
      timeLimit: 120
    },
    {
      id: 'tech-do-003',
      type: 'open-ended',
      content: "What is Kubernetes and why is it used? Can you explain pods and deployments?",
      difficulty: 'hard',
      topic: 'Kubernetes',
      timeLimit: 150
    }
  ]
};

// Coding questions for each domain
export const codingQuestions: Record<string, Question[]> = {
  dsa: [
    {
      id: 'code-dsa-001',
      type: 'coding',
      content: `## Two Sum Problem

Given an array of integers \`nums\` and an integer \`target\`, return indices of the two numbers such that they add up to target.

You may assume that each input would have exactly one solution, and you may not use the same element twice.

### Example 1:
\`\`\`
Input: nums = [2,7,11,15], target = 9
Output: [0,1]
Explanation: nums[0] + nums[1] == 9
\`\`\`

### Example 2:
\`\`\`
Input: nums = [3,2,4], target = 6
Output: [1,2]
\`\`\`

### Constraints:
- 2 ≤ nums.length ≤ 10⁴
- -10⁹ ≤ nums[i] ≤ 10⁹
- -10⁹ ≤ target ≤ 10⁹`,
      difficulty: 'easy',
      topic: 'Arrays',
      timeLimit: 900,
      codeTemplate: `def two_sum(nums: list[int], target: int) -> list[int]:
    # Write your solution here
    pass`,
      testCases: [
        { id: 'tc-1', input: '[2,7,11,15], 9', expectedOutput: '[0,1]', isHidden: false },
        { id: 'tc-2', input: '[3,2,4], 6', expectedOutput: '[1,2]', isHidden: false },
        { id: 'tc-3', input: '[3,3], 6', expectedOutput: '[0,1]', isHidden: true }
      ]
    }
  ],
  'system-design': [
    {
      id: 'code-sd-001',
      type: 'coding',
      content: `## Design a Rate Limiter

Implement a simple rate limiter class that limits the number of requests a user can make in a given time window.

### Requirements:
- \`RateLimiter(max_requests, window_seconds)\`: Initialize with max requests allowed per window
- \`is_allowed(user_id)\`: Returns True if the user can make a request, False otherwise

### Example:
\`\`\`
limiter = RateLimiter(3, 60)  # 3 requests per 60 seconds
limiter.is_allowed("user1")   # True
limiter.is_allowed("user1")   # True
limiter.is_allowed("user1")   # True
limiter.is_allowed("user1")   # False (exceeded limit)
\`\`\``,
      difficulty: 'medium',
      topic: 'Rate Limiting',
      timeLimit: 1200,
      codeTemplate: `import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        # Initialize your rate limiter
        pass
    
    def is_allowed(self, user_id: str) -> bool:
        # Check if request is allowed
        pass`,
      testCases: [
        { id: 'tc-1', input: 'RateLimiter(2, 60), 3 calls for user1', expectedOutput: '[True, True, False]', isHidden: false }
      ]
    }
  ],
  backend: [
    {
      id: 'code-be-001',
      type: 'coding',
      content: `## Implement a Simple Cache

Create a Least Recently Used (LRU) Cache with a fixed capacity.

### Requirements:
- \`LRUCache(capacity)\`: Initialize the cache with positive capacity
- \`get(key)\`: Return the value if key exists, otherwise return -1
- \`put(key, value)\`: Insert or update the value. Remove least recently used item if capacity exceeded.

### Example:
\`\`\`
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
cache.get(1)       # returns 1
cache.put(3, 3)    # removes key 2
cache.get(2)       # returns -1 (not found)
\`\`\``,
      difficulty: 'medium',
      topic: 'Caching',
      timeLimit: 1200,
      codeTemplate: `class LRUCache:
    def __init__(self, capacity: int):
        # Initialize your cache
        pass
    
    def get(self, key: int) -> int:
        # Get value from cache
        pass
    
    def put(self, key: int, value: int) -> None:
        # Put value in cache
        pass`,
      testCases: [
        { id: 'tc-1', input: 'LRUCache(2), put(1,1), put(2,2), get(1)', expectedOutput: '1', isHidden: false }
      ]
    }
  ],
  frontend: [
    {
      id: 'code-fe-001',
      type: 'coding',
      content: `## Debounce Function

Implement a debounce function that delays invoking a function until after a specified wait time has elapsed since the last time it was invoked.

### Requirements:
- \`debounce(func, wait)\`: Returns a debounced version of the function
- Multiple rapid calls should only execute the function once after the wait period

### Example:
\`\`\`javascript
const debouncedLog = debounce(console.log, 1000);
debouncedLog("Hello");  // Called at t=0
debouncedLog("World");  // Called at t=500ms, cancels previous
// "World" is logged at t=1500ms
\`\`\``,
      difficulty: 'medium',
      topic: 'JavaScript',
      timeLimit: 900,
      codeTemplate: `function debounce(func, wait) {
  // Implement debounce
}`,
      testCases: [
        { id: 'tc-1', input: 'debounce(fn, 100), call 3 times in 50ms', expectedOutput: 'fn called once', isHidden: false }
      ]
    }
  ],
  behavioral: [
    {
      id: 'code-beh-001',
      type: 'coding',
      content: `## FizzBuzz

Write a function that prints numbers from 1 to n. For multiples of 3, print "Fizz". For multiples of 5, print "Buzz". For multiples of both, print "FizzBuzz".

### Example:
\`\`\`
Input: n = 15
Output: 1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz
\`\`\``,
      difficulty: 'easy',
      topic: 'Logic',
      timeLimit: 600,
      codeTemplate: `def fizzbuzz(n: int) -> list[str]:
    # Write your solution here
    pass`,
      testCases: [
        { id: 'tc-1', input: '5', expectedOutput: '["1", "2", "Fizz", "4", "Buzz"]', isHidden: false }
      ]
    }
  ],
  devops: [
    {
      id: 'code-do-001',
      type: 'coding',
      content: `## Parse Log File

Write a function to parse a log file and count occurrences of each log level (INFO, WARN, ERROR).

### Log Format:
\`\`\`
[2024-01-15 10:30:00] INFO: Application started
[2024-01-15 10:30:05] ERROR: Database connection failed
[2024-01-15 10:30:10] WARN: Retrying connection
\`\`\`

### Example:
\`\`\`
Input: log_content (string)
Output: {"INFO": 1, "WARN": 1, "ERROR": 1}
\`\`\``,
      difficulty: 'easy',
      topic: 'Log Parsing',
      timeLimit: 600,
      codeTemplate: `def parse_logs(log_content: str) -> dict:
    # Parse the logs and count levels
    pass`,
      testCases: [
        { id: 'tc-1', input: 'Sample log with 2 INFO, 1 ERROR', expectedOutput: '{"INFO": 2, "ERROR": 1, "WARN": 0}', isHidden: false }
      ]
    }
  ]
};

// Complexity analysis questions (asked after coding)
export const complexityQuestions: Question[] = [
  {
    id: 'complexity-001',
    type: 'open-ended',
    content: "Great work on the coding problem! Now, can you analyze the time complexity of your solution? What is the Big O notation and why?",
    difficulty: 'medium',
    topic: 'Time Complexity',
    timeLimit: 90
  },
  {
    id: 'complexity-002',
    type: 'open-ended',
    content: "What about the space complexity of your solution? How much additional memory does your algorithm use?",
    difficulty: 'medium',
    topic: 'Space Complexity',
    timeLimit: 90
  },
  {
    id: 'complexity-003',
    type: 'open-ended',
    content: "Can you think of any ways to optimize your solution further? Are there any trade-offs between time and space complexity?",
    difficulty: 'hard',
    topic: 'Optimization',
    timeLimit: 120
  }
];

// Get questions for interview flow based on type
export const getInterviewFlow = (interviewType: string): {
  intro: Question;
  technical: Question[];
  coding: Question;
  complexity: Question[];
} => {
  const techQs = technicalQuestions[interviewType] || technicalQuestions['dsa'];
  const codeQs = codingQuestions[interviewType] || codingQuestions['dsa'];
  
  return {
    intro: selfIntroQuestion,
    technical: techQs.slice(0, 2), // Take 2 technical questions
    coding: codeQs[0], // Take 1 coding question
    complexity: complexityQuestions.slice(0, 2) // Take 2 complexity questions
  };
};
