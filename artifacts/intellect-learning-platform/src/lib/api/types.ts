export type User = { id: number; name: string; role: 'student' | 'teacher'; grade: number | null };
export type LoginUsers = { students: User[]; teachers: User[] };
export type Subject = { id: number; name: string; grade: number; hours_per_week: number; hours_per_year: number; source_info: string | null; instruction_language?: 'ru' | 'ky'; progress?: number };
export type Section = { id: number; subject_id: number; name: string; sort_order: number; total_hours: number };
export type Topic = { id: number; section_id: number; ktp_number: string | null; name: string; hours: number; lesson_type: string; learning_objectives: string | null; skills: string[]; resources: string | null; lesson_id?: number | null; lesson_status?: 'draft' | 'published' | null };
export type SectionOutline = Section & { topics: Topic[] };
export type LearningObjective = {
  id: string;
  text: string;
  success_criteria?: string;
};
export type ObjectiveEvidence = {
  objective_id: string;
  block_index?: number;
  stage?: 'diagnostic' | 'explanation' | 'practice' | 'assessment' | string;
  correct?: boolean;
  score?: number;
  attempts?: number;
};
export type MasteryStatus = 'not_assessed' | 'in_progress' | 'mastered' | 'needs_practice';
export type ObjectiveMastery = {
  status: MasteryStatus;
  score?: number;
  diagnostic_passed?: boolean;
  final_passed?: boolean;
};
export type QualityReport = {
  publishable?: boolean;
  objectives?: Record<string, {
    objective?: string;
    diagnostic?: number[];
    explanation?: number[];
    practice?: number[];
    assessment?: number[];
    evidence?: Array<{ block: number; stage: string }>;
  }>;
  gaps?: Array<{ objective_id?: string; objective?: string; missing?: string[] } | string>;
  errors?: Array<{ code?: string; block?: number; message?: string } | string>;
  warnings?: Array<{ code?: string; block?: number; message?: string } | string>;
  legacy?: boolean;
};
export type ObjectiveResult = {
  status: MasteryStatus;
  score?: number;
  evidence?: ObjectiveEvidence[];
};
export type ProgressRecord = { id: number; student_id: number; topic_id: number; status: 'not_started' | 'in_progress' | 'completed'; score: number | null; mastery_level: string | null; mastery_status?: MasteryStatus; objective_mastery?: Record<string, ObjectiveMastery>; objective_evidence?: Record<string, ObjectiveEvidence[]>; time_spent_sec: number; attempts: number; current_step: number; max_opened_step: number; answers: Record<string, boolean>; attempts_by_step: Record<string, number>; elapsed_time_sec: number; };
export type DashboardOverview = { students: number; subjects: number; topics: number; published_lessons: number; average_progress: number };
export type StudentSummary = { id: number; name: string; grade: number; completed_topics: number; average_score: number };
export type ComponentSchema = {
  type?: string;
  enum?: string[];
  required?: string[];
  minItems?: number;
  maxItems?: number;
  properties?: Record<string, ComponentSchema>;
  items?: ComponentSchema;
};
export type ComponentRegistryEntry = {
  id: string;
  code: string;
  category: string;
  subjects: string[];
  purpose: string;
  is_assessment: boolean;
  content_schema: ComponentSchema;
  rendering_notes: string;
};
export type Block = {
  component: string;
  content: Record<string, unknown>;
};
export type GeneratedLesson = {
  id: number;
  topic_id: number;
  blocks: Block[];
  lesson_metadata: Record<string, unknown> & {
    objectives?: LearningObjective[];
    quality_report?: QualityReport;
    legacy_review_required?: boolean;
  };
  status: 'draft' | 'published';
  generated_at: string;
  published_at: string | null;
  published_by: number | null;
  model_used: string | null;
};
