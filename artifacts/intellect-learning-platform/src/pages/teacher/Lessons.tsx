import { CreateCourse } from '@/features/teacherLessons/CreateCourse';
import { GardenLessonCard } from '@/features/visualLesson/GardenLessonCard';
import { useState } from 'react';
import { useSubjects } from '@/lib/api';
import { NoSubjectSelected, SectionsList, SubjectTabs } from '@/features/teacherLessons/listViews';
import { KtpImportButton } from '@/features/teacherLessons/KtpImport';
import { subjectGrades, subjectsForGrade } from '@/features/teacherLessons/listModel';
import { CurriculumGraphPanel } from '@/features/teacherLessons/CurriculumGraphPanel';

export default function Lessons() {
  const { data: subjects, isLoading: loadingSubs } = useSubjects();
  const [selectedSubject, setSelectedSubject] = useState<number | null>(() => Number(sessionStorage.getItem('teacher-subject')) || null);
  const [selectedGrade, setSelectedGrade] = useState<number | null>(() => Number(sessionStorage.getItem('teacher-grade')) || null);
  const grades = subjectGrades(subjects);
  const activeGrade = selectedGrade ?? grades[0] ?? null;
  const visibleSubjects = subjectsForGrade(subjects, activeGrade);

  const selectGrade = (grade: number) => {
    sessionStorage.setItem('teacher-grade', String(grade));
    sessionStorage.removeItem('teacher-subject');
    setSelectedGrade(grade);
    setSelectedSubject(null);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Управление уроками</h1>
          <p className="text-muted-foreground mt-2 font-medium">Редактируйте материалы и структуру курсов</p>
        </div>
        <div className="flex flex-wrap gap-3"><CreateCourse onCreated={(id, grade) => {
          setSelectedSubject(id); setSelectedGrade(grade);
          sessionStorage.setItem('teacher-subject', String(id)); sessionStorage.setItem('teacher-grade', String(grade));
        }} /><KtpImportButton /></div>
      </div>

      <GardenLessonCard />
      {grades.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto border-b border-border pb-3" aria-label="Класс программы">
          <span className="mr-2 shrink-0 text-sm font-semibold text-muted-foreground">Класс</span>
          {grades.map((grade) => (
            <button
              key={grade}
              type="button"
              onClick={() => selectGrade(grade)}
              aria-pressed={activeGrade === grade}
              className={`h-10 min-w-12 shrink-0 border px-4 text-sm font-bold transition-colors ${
                activeGrade === grade
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground'
              }`}
            >
              {grade}
            </button>
          ))}
        </div>
      )}

      <SubjectTabs
        isLoading={loadingSubs}
        selectedSubject={selectedSubject}
        subjects={visibleSubjects}
        onSelect={id => { setSelectedSubject(id); sessionStorage.setItem('teacher-subject', String(id)); }}
      />

      {selectedSubject && <SectionsList subjectId={selectedSubject} />}
      {selectedSubject && <CurriculumGraphPanel subjectId={selectedSubject} />}
      {!selectedSubject && visibleSubjects.length > 0 && (
        <NoSubjectSelected />
      )}
    </div>
  );
}
