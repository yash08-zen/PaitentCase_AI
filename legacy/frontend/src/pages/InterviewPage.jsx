import { useState, useEffect, useCallback } from 'react';
import { interviewsApi } from '../services/api';
import './InterviewPage.css';

const GROUP_LABELS = {
  core:        '📋 Core Information',
  symptoms:    '🩺 Symptoms',
  history:     '📁 Medical History',
  medications: '💊 Medications',
  allergies:   '⚠ Allergies',
};

export default function InterviewPage({ encounterId, onNavigate }) {
  const [state, setState] = useState({
    question: null,
    progress: 0,
    isComplete: false,
  });
  const [answer, setAnswer] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]); // [{question_key, answer}]

  const loadNext = useCallback(async () => {
    try {
      const data = await interviewsApi.nextQuestion(encounterId);
      setState({ question: data.question, progress: data.progress, isComplete: data.is_complete });
      setAnswer('');
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }, [encounterId]);

  useEffect(() => {
    // Resume existing interview
    interviewsApi.resume(encounterId).then(data => {
      setState({ question: data.question, progress: data.progress, isComplete: data.is_complete });
    }).catch(() => loadNext());
  }, [encounterId, loadNext]);

  async function handleSubmit() {
    if (!answer.trim()) { setError('Please provide an answer before continuing.'); return; }
    setError('');
    setSubmitting(true);
    setSaving(true);
    try {
      await interviewsApi.submitResponse(encounterId, state.question.key, answer.trim());
      setHistory(h => [...h, { key: state.question.key, text: state.question.text, answer: answer.trim() }]);
      await loadNext();
    } catch (err) {
      setError(err.message || 'Failed to save response. Please try again.');
    } finally {
      setSubmitting(false);
      setTimeout(() => setSaving(false), 1500);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey && state.question?.answer_type !== 'text') {
      e.preventDefault();
      handleSubmit();
    }
  }

  const pct = Math.round(state.progress * 100);

  if (state.isComplete) {
    return (
      <div className="interview-root">
        <div className="interview-card interview-complete animate-fade">
          <div className="interview-complete-icon">🎉</div>
          <h2>Interview Complete</h2>
          <p className="mt-md" style={{ maxWidth: 400, margin: '16px auto 0' }}>
            All questions have been answered. The case information has been saved and is ready for review.
          </p>
          <div className="flex gap-sm justify-center mt-lg" style={{ flexWrap: 'wrap' }}>
            <button className="btn btn-primary" onClick={() => onNavigate('case-review', { encounterId })}>
              View Case Summary →
            </button>
            <button className="btn btn-secondary" onClick={() => onNavigate('dashboard')}>
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!state.question && !state.isComplete) {
    return (
      <div className="page-content">
        <div className="loading-center"><div className="loader loader-lg" /><p>Loading interview…</p></div>
      </div>
    );
  }

  const q = state.question;

  return (
    <div className="interview-root">
      <div className="interview-header">
        <div className="interview-meta">
          <span className="text-muted text-sm">Encounter #{encounterId}</span>
          <div className="interview-progress-label">{pct}% complete</div>
          {saving && (
            <span className="interview-saving-dot">
              <span className="saving-dot" /> Saved
            </span>
          )}
        </div>

        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>

        {pct > 0 && (
          <div style={{ marginTop: 6, fontSize: '0.75rem', color: 'var(--c-text-dim)' }}>
            {history.length} question{history.length !== 1 ? 's' : ''} answered
          </div>
        )}
      </div>

      <div className="interview-card">
        {q.group && (
          <div className="interview-group-tag">
            {GROUP_LABELS[q.group] || q.group}
          </div>
        )}

        <div className="interview-question" role="heading" aria-level={2}>
          {q.text}
          {q.is_required && <span className="required" style={{ marginLeft: 6 }}>*</span>}
        </div>

        <div className="interview-answer-area">
          {error && <div className="alert alert-danger">⚠ {error}</div>}

          {/* Choice question */}
          {q.answer_type === 'choice' && q.choices && (
            <div className="choice-grid" onKeyDown={handleKeyDown}>
              {q.choices.map(choice => (
                <button
                  key={choice}
                  className={`choice-btn ${answer === choice ? 'selected' : ''}`}
                  onClick={() => { setAnswer(choice); setError(''); }}
                  type="button"
                  aria-pressed={answer === choice}
                >
                  {answer === choice ? '✓ ' : ''}{choice}
                </button>
              ))}
            </div>
          )}

          {/* Text question */}
          {q.answer_type === 'text' && (
            <textarea
              className="form-textarea"
              placeholder="Type your answer here…"
              value={answer}
              onChange={e => { setAnswer(e.target.value); setError(''); }}
              rows={4}
              autoFocus
            />
          )}

          {/* Number question */}
          {q.answer_type === 'number' && (
            <input
              className="form-input"
              type="number"
              placeholder="Enter a number"
              value={answer}
              onChange={e => { setAnswer(e.target.value); setError(''); }}
              onKeyDown={handleKeyDown}
              autoFocus
            />
          )}

          {/* Date question */}
          {q.answer_type === 'date' && (
            <input
              className="form-input"
              type="date"
              value={answer}
              onChange={e => { setAnswer(e.target.value); setError(''); }}
              autoFocus
            />
          )}
        </div>

        <div className="interview-nav">
          <button
            className="btn btn-ghost"
            onClick={() => onNavigate('dashboard')}
            type="button"
          >
            ← Save & Exit
          </button>

          <button
            id="interview-next"
            className="btn btn-primary btn-lg"
            onClick={handleSubmit}
            disabled={submitting || !answer.trim()}
            type="button"
          >
            {submitting
              ? <><span className="loader" /> Saving…</>
              : 'Next →'}
          </button>
        </div>
      </div>

      {/* Previous answers accordion */}
      {history.length > 0 && (
        <details style={{ marginTop: 'var(--sp-lg)' }}>
          <summary style={{ cursor: 'pointer', color: 'var(--c-text-muted)', fontSize: '0.85rem', padding: '8px 0' }}>
            View previous answers ({history.length})
          </summary>
          <div className="card" style={{ marginTop: 8 }}>
            {history.map((h, i) => (
              <div key={i} style={{
                padding: '10px 0',
                borderBottom: i < history.length - 1 ? '1px solid var(--c-border-subtle)' : 'none',
              }}>
                <div className="text-sm text-muted">{h.text}</div>
                <div style={{ fontWeight: 600, marginTop: 4 }}>{h.answer}</div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
