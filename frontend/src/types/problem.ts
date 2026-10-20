export interface ProblemStructureRequest {
  problem_text: string
}

export interface ProblemExample {
  input: string
  output: string
  explanation: string | null
}

export interface StructuredProblem {
  title: string | null
  goal: string
  input_format: string | null
  output_format: string | null
  constraints: string[]
  examples: ProblemExample[]
  ambiguities: string[]
}
