import React, { useState, useMemo } from 'react';
import { LineChart, Line, BarChart, Bar, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { parseMathText } from './ShortExplanation';

export interface InteractiveParam {
  name: string;
  label: string;
  min: number;
  max: number;
  step: number;
  default: number;
  formula_description: string;
}

export interface DataPoint {
  x: number;
  y: number;
  label?: string;
}

export interface InteractiveGraphProps {
  title: string;
  description: string;
  graph_type: 'line' | 'bar' | 'scatter';
  data_points: DataPoint[];
  x_label: string;
  y_label: string;
  interactive_params?: InteractiveParam[];
}

export default function InteractiveGraph({ title, description, graph_type, data_points, x_label, y_label, interactive_params }: InteractiveGraphProps) {
  const [paramValues, setParamValues] = useState<Record<string, number>>(() => {
    const init: Record<string, number> = {};
    if (interactive_params) {
      interactive_params.forEach(p => init[p.name] = p.default);
    }
    return init;
  });

  const handleParamChange = (name: string, value: number) => {
    setParamValues(prev => ({ ...prev, [name]: value }));
  };

  const scaledData = useMemo(() => {
    let scaleFactor = 1;
    if (interactive_params) {
      interactive_params.forEach(p => {
        const val = paramValues[p.name];
        const def = p.default;
        if (def !== 0) {
          scaleFactor *= (val / def);
        } else if (val !== 0) {
          scaleFactor *= val;
        }
      });
    }
    
    return data_points.map(dp => ({
      ...dp,
      scaledY: dp.y * scaleFactor
    }));
  }, [data_points, paramValues, interactive_params]);

  const renderChart = () => {
    const margin = { top: 20, right: 30, left: 20, bottom: 20 };
    
    switch (graph_type) {
      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={scaledData} margin={margin}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="x" label={{ value: x_label, position: 'insideBottom', offset: -10 }} />
              <YAxis label={{ value: y_label, angle: -90, position: 'insideLeft' }} />
              <Tooltip cursor={{ fill: 'hsl(var(--muted)/0.5)' }} />
              <Bar dataKey="scaledY" name={y_label} fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        );
      case 'scatter':
        return (
          <ResponsiveContainer width="100%" height={400}>
            <ScatterChart margin={margin}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" type="number" name={x_label} label={{ value: x_label, position: 'insideBottom', offset: -10 }} />
              <YAxis dataKey="scaledY" type="number" name={y_label} label={{ value: y_label, angle: -90, position: 'insideLeft' }} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              <Scatter name={y_label} data={scaledData} fill="hsl(var(--primary))" />
            </ScatterChart>
          </ResponsiveContainer>
        );
      case 'line':
      default:
        return (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={scaledData} margin={margin}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="x" label={{ value: x_label, position: 'insideBottom', offset: -10 }} />
              <YAxis label={{ value: y_label, angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Line type="monotone" dataKey="scaledY" stroke="hsl(var(--primary))" activeDot={{ r: 8 }} strokeWidth={2} name={y_label} />
            </LineChart>
          </ResponsiveContainer>
        );
    }
  };

  return (
    <div className="border rounded-xl p-6 my-6 bg-card shadow-sm">
      <h3 className="font-semibold text-lg mb-2 text-foreground">{title}</h3>
      <div className="text-muted-foreground text-sm mb-6 whitespace-pre-wrap">
        {parseMathText(description)}
      </div>

      <div className="bg-background rounded-lg border p-4 mb-6">
        {renderChart()}
      </div>

      {interactive_params && interactive_params.length > 0 && (
        <div className="space-y-6 bg-muted/20 p-5 rounded-lg border">
          <h4 className="font-medium text-sm text-foreground mb-4">Параметры графика</h4>
          {interactive_params.map(param => (
            <div key={param.name} className="space-y-3">
              <div className="flex justify-between items-center text-sm">
                <label htmlFor={`param-${param.name}`} className="font-medium text-foreground">
                  {param.label}
                </label>
                <span className="font-mono text-primary bg-primary/10 px-2 py-0.5 rounded">
                  {paramValues[param.name].toFixed(2)}
                </span>
              </div>
              <input
                id={`param-${param.name}`}
                type="range"
                min={param.min}
                max={param.max}
                step={param.step}
                value={paramValues[param.name]}
                onChange={(e) => handleParamChange(param.name, parseFloat(e.target.value))}
                className="w-full accent-primary"
              />
              {param.formula_description && (
                <div className="text-xs text-muted-foreground italic mt-1">
                  {parseMathText(param.formula_description)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
