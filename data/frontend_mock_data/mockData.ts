import type { Interview, Candidate, InterviewTemplate, Question } from '@/types/interview';

export const mockCandidate: Candidate = {
  id: 'cand-001',
  name: 'Alex Johnson',
  email: 'alex.johnson@email.com',
  phone: '+1 (555) 123-4567',
  role: 'Senior Backend Engineer',
  experienceYears: 5,
  skills: ['Python', 'Java', 'System Design', 'Kubernetes', 'PostgreSQL', 'Redis'],
  profileImage: undefined
};

export const interviewTemplates: InterviewTemplate[] = [
  {
    id: 'template-dsa',
    name: 'DSA Fundamentals',
    type: 'dsa',
    description: 'Data Structures & Algorithms assessment covering arrays, trees, graphs, and dynamic programming',
    duration: 60,
    questionCount: 4,
    difficultyDistribution: { easy: 1, medium: 2, hard: 1 },
    topics: ['Arrays', 'Trees', 'Graphs', 'Dynamic Programming', 'Hash Maps']
  },
  {
    id: 'template-system-design',
    name: 'System Design',
    type: 'system-design',
    description: 'Design scalable distributed systems with focus on architecture and trade-offs',
    duration: 90,
    questionCount: 2,
    difficultyDistribution: { easy: 0, medium: 1, hard: 1 },
    topics: ['Scalability', 'Database Design', 'Caching', 'Load Balancing', 'Microservices']
  },
  {
    id: 'template-backend',
    name: 'Backend Engineering',
    type: 'backend',
    description: 'Server-side development covering APIs, databases, and backend patterns',
    duration: 75,
    questionCount: 5,
    difficultyDistribution: { easy: 1, medium: 3, hard: 1 },
    topics: ['REST APIs', 'Database Design', 'Authentication', 'Caching', 'Testing']
  },
  {
    id: 'template-frontend',
    name: 'Frontend Development',
    type: 'frontend',
    description: 'Modern frontend development with React, state management, and performance',
    duration: 60,
    questionCount: 4,
    difficultyDistribution: { easy: 1, medium: 2, hard: 1 },
    topics: ['React', 'State Management', 'Performance', 'Accessibility', 'CSS']
  },
  {
    id: 'template-behavioral',
    name: 'Behavioral Interview',
    type: 'behavioral',
    description: 'Assess leadership, communication, and problem-solving through behavioral questions',
    duration: 45,
    questionCount: 6,
    difficultyDistribution: { easy: 2, medium: 3, hard: 1 },
    topics: ['Leadership', 'Conflict Resolution', 'Teamwork', 'Problem Solving']
  },
  {
    id: 'template-devops',
    name: 'DevOps & Cloud',
    type: 'devops',
    description: 'Cloud infrastructure, CI/CD, containerization, and DevOps practices',
    duration: 60,
    questionCount: 4,
    difficultyDistribution: { easy: 1, medium: 2, hard: 1 },
    topics: ['Docker', 'Kubernetes', 'CI/CD', 'AWS/GCP', 'Terraform']
  }
];

export const mockQuestions: Question[] = [
  {
    id: 'q-001',
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
  },
  {
    id: 'q-002',
    type: 'open-ended',
    content: `## REST API Design

Explain how you would design a RESTful API for a social media platform's post system. 

Consider:
- Resource naming conventions
- HTTP methods and their usage
- Pagination strategy
- Error handling approach
- Authentication considerations`,
    difficulty: 'medium',
    topic: 'REST APIs',
    timeLimit: 600
  },
  {
    id: 'q-003',
    type: 'system-design',
    content: `## Design a URL Shortener

Design a URL shortening service like bit.ly or tinyurl.

Your design should include:
1. **Functional Requirements**: Create short URL, redirect, analytics
2. **Non-functional Requirements**: High availability, low latency
3. **System Components**: API, database, caching layer
4. **Scalability**: Handle 100M+ URLs, 1B+ redirects/month

Walk through your approach step by step.`,
    difficulty: 'hard',
    topic: 'System Design',
    timeLimit: 1800
  },
  {
    id: 'q-004',
    type: 'coding',
    content: `## Valid Parentheses

Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.

An input string is valid if:
1. Open brackets must be closed by the same type of brackets.
2. Open brackets must be closed in the correct order.
3. Every close bracket has a corresponding open bracket of the same type.

### Examples:
\`\`\`
Input: s = "()"      Output: true
Input: s = "()[]{}"  Output: true
Input: s = "(]"      Output: false
\`\`\``,
    difficulty: 'easy',
    topic: 'Stack',
    timeLimit: 600,
    codeTemplate: `def isValid(s: str) -> bool:
    # Write your solution here
    pass`,
    testCases: [
      { id: 'tc-1', input: '"()"', expectedOutput: 'true', isHidden: false },
      { id: 'tc-2', input: '"()[]{}"', expectedOutput: 'true', isHidden: false },
      { id: 'tc-3', input: '"(]"', expectedOutput: 'false', isHidden: false }
    ]
  }
];

export const mockInterviewHistory: Interview[] = [
  {
    id: 'int-001',
    candidateId: 'cand-001',
    type: 'dsa',
    status: 'completed',
    scheduledAt: new Date('2025-01-18T10:00:00'),
    startedAt: new Date('2025-01-18T10:02:00'),
    completedAt: new Date('2025-01-18T11:05:00'),
    duration: 60,
    role: 'Backend Engineer',
    company: 'TechCorp',
    experienceLevel: '3-5 years',
    questions: mockQuestions.slice(0, 2),
    answers: [],
    evaluations: [],
    overallScore: 85,
    overallFeedback: 'Strong problem-solving skills with good understanding of data structures. Could improve on time complexity analysis.'
  },
  {
    id: 'int-002',
    candidateId: 'cand-001',
    type: 'system-design',
    status: 'completed',
    scheduledAt: new Date('2025-01-15T14:00:00'),
    startedAt: new Date('2025-01-15T14:05:00'),
    completedAt: new Date('2025-01-15T15:35:00'),
    duration: 90,
    role: 'Senior Backend Engineer',
    company: 'ScaleUp Inc',
    experienceLevel: '5+ years',
    questions: [mockQuestions[2]],
    answers: [],
    evaluations: [],
    overallScore: 78,
    overallFeedback: 'Good understanding of distributed systems. Recommendations for deeper exploration of caching strategies and database sharding.'
  },
  {
    id: 'int-003',
    candidateId: 'cand-001',
    type: 'backend',
    status: 'scheduled',
    scheduledAt: new Date('2025-01-22T09:00:00'),
    duration: 75,
    role: 'Backend Engineer',
    company: 'StartupXYZ',
    experienceLevel: '3-5 years',
    questions: [],
    answers: [],
    evaluations: []
  }
];

export const upcomingInterviews = [
  {
    id: 'upcoming-1',
    type: 'backend' as const,
    company: 'StartupXYZ',
    role: 'Backend Engineer',
    scheduledAt: new Date('2025-01-22T09:00:00'),
    duration: 75
  },
  {
    id: 'upcoming-2',
    type: 'behavioral' as const,
    company: 'TechGiant',
    role: 'Senior SWE',
    scheduledAt: new Date('2025-01-25T14:00:00'),
    duration: 45
  }
];

export const performanceStats = {
  totalInterviews: 12,
  averageScore: 82,
  strongAreas: ['Arrays', 'Hash Maps', 'REST APIs'],
  improvementAreas: ['Dynamic Programming', 'System Design'],
  recentScores: [78, 85, 72, 88, 82, 90],
  skillBreakdown: {
    'Problem Solving': 85,
    'Communication': 78,
    'Technical Knowledge': 82,
    'Code Quality': 88,
    'System Design': 72
  }
};
