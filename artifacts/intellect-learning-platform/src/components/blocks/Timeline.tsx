import React from 'react';
import { parseMathText } from './ShortExplanation';

export interface TimelineEvent {
  date: string;
  label: string;
  description?: string;
}

export interface TimelineProps {
  title: string;
  events: TimelineEvent[];
}

export default function Timeline({ title, events }: TimelineProps) {
  if (!events || events.length === 0) return null;

  return (
    <div className="my-10 w-full overflow-hidden relative">
      <h3 className="font-semibold text-lg text-foreground mb-6 px-4">{title}</h3>
      
      <div className="absolute left-0 top-14 bottom-0 w-8 bg-gradient-to-r from-background to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-14 bottom-0 w-8 bg-gradient-to-l from-background to-transparent z-10 pointer-events-none" />
      
      <div className="overflow-x-auto custom-scrollbar pb-8 px-8 -mx-8 scroll-smooth snap-x snap-mandatory">
        <div className="flex min-w-max relative pt-16 pb-6 items-start">
          <div className="absolute top-[88px] left-8 right-8 h-0.5 bg-border z-0" />
          
          {events.map((event, i) => (
            <div 
              key={i} 
              className="relative flex flex-col items-center w-72 px-4 snap-center group z-10"
            >
              <div className="absolute top-0 text-sm font-bold text-primary bg-background px-3 py-1 rounded-full border border-primary/20 shadow-sm mb-6 z-20">
                {event.date}
              </div>
              
              <div className="w-5 h-5 mt-14 rounded-full bg-background border-4 border-primary group-hover:scale-125 group-hover:border-secondary transition-all duration-300 z-10 shadow-sm" />
              
              <div className="h-4 w-px bg-border my-2 opacity-50" />
              
              <div className="bg-card border rounded-xl p-5 w-full text-center shadow-sm hover:shadow-md transition-all duration-300 group-hover:border-primary/40 relative">
                <h4 className="font-semibold text-foreground text-base leading-tight mb-2">{event.label}</h4>
                {event.description && (
                  <div className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap mt-3 pt-3 border-t">
                    {parseMathText(event.description)}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
