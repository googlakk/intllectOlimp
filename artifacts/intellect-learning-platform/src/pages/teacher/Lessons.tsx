import { useState, useRef } from 'react';
import { useSubjects } from '@/lib/api';
import { FileUp, Loader2 } from 'lucide-react';
import { NoSubjectSelected, SectionsList, SubjectTabs } from '@/features/teacherLessons/listViews';
import { useKtpUploadWorkflow } from '@/features/teacherLessons/uploadWorkflow';

export default function Lessons() {
  const { data: subjects, isLoading: loadingSubs } = useSubjects();
  const [selectedSubject, setSelectedSubject] = useState<number | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetFileInput = () => {
    if (fileInputRef.current) fileInputRef.current.value = '';
  };
  const {
    error: uploadError,
    isUploading,
    success: uploadSuccess,
    uploadFile,
  } = useKtpUploadWorkflow(resetFileInput);

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    void uploadFile(e.target.files?.[0]);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Управление уроками</h1>
          <p className="text-muted-foreground mt-2 font-medium">Редактируйте материалы и структуру курсов</p>
          {uploadError && <p className="text-destructive text-sm mt-2 font-bold">{uploadError}</p>}
          {uploadSuccess && <p className="text-green-600 text-sm mt-2 font-bold">{uploadSuccess}</p>}
        </div>
        <input type="file" ref={fileInputRef} className="hidden" accept=".json" onChange={handleUpload} />
        <button 
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground font-bold rounded-xl shadow-md shadow-primary/20 hover:bg-primary/90 transition-all disabled:opacity-70"
        >
          {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileUp className="w-5 h-5" />}
          {isUploading ? 'Загрузка...' : 'Загрузить КТП (JSON)'}
        </button>
      </div>

      <SubjectTabs
        isLoading={loadingSubs}
        selectedSubject={selectedSubject}
        subjects={subjects}
        onSelect={setSelectedSubject}
      />

      {selectedSubject && <SectionsList subjectId={selectedSubject} />}
      {!selectedSubject && subjects && subjects.length > 0 && (
        <NoSubjectSelected />
      )}
    </div>
  );
}
