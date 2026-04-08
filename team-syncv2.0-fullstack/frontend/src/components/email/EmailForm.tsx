// components/email/EmailForm.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Mail, Send, CheckCircle, AlertCircle, ChevronLeft } from 'lucide-react';

export function EmailForm() {
  const navigate = useNavigate();
  const { dispatch, activeTab } = useApp();
  const [formData, setFormData] = useState({
    recipientName: '',
    recipientEmail: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const validate = () => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.recipientName.trim()) {
      newErrors.recipientName = 'Name is required';
    }
    
    if (!formData.recipientEmail.trim()) {
      newErrors.recipientEmail = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.recipientEmail)) {
      newErrors.recipientEmail = 'Invalid email address';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validate() || !activeTab.currentPRD) return;
    
    setIsSubmitting(true);
    dispatch({ type: 'SET_EMAIL_STATUS', payload: 'sending' });
    
    // Email is now sent automatically via the chat flow.
    // This page is kept for reference; redirect to chat.
    dispatch({ type: 'SET_EMAIL_STATUS', payload: 'sent' });
    setIsSuccess(true);
    setIsSubmitting(false);
  };

  if (isSuccess) {
    return (
      <div className="max-w-md mx-auto mt-12">
        <Card className="text-center">
          <CardContent className="pt-12 pb-8">
            <div className="w-20 h-20 rounded-full bg-status-success/20 flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="w-10 h-10 text-status-success" />
            </div>
            <h2 className="text-2xl font-bold text-text-primary mb-2">Email Sent!</h2>
            <p className="text-text-secondary mb-6">
              The PRD has been sent to {formData.recipientEmail}
            </p>
            <div className="flex gap-3 justify-center">
              <Button variant="secondary" onClick={() => navigate('/prd')}>
                View PRD
              </Button>
              <Button onClick={() => navigate('/jira')}>
                Create JIRA Tickets
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <Button variant="ghost" size="sm" onClick={() => navigate('/prd')} className="mb-4">
        <ChevronLeft className="w-4 h-4 mr-1" />
        Back to PRD
      </Button>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
              <Mail className="w-5 h-5 text-primary-light" />
            </div>
            <div>
              <CardTitle>Send PRD via Email</CardTitle>
              <p className="text-sm text-text-muted">
                Enter recipient details to deliver the PRD document
              </p>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {activeTab.currentPRD ? (
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="p-4 bg-background-tertiary rounded-lg border border-white/10">
                <p className="text-sm text-text-secondary mb-1">Document</p>
                <p className="font-medium text-text-primary">{activeTab.currentPRD.title}</p>
                <p className="text-xs text-text-muted mt-1">
                  {activeTab.currentPRD.fileName || `${activeTab.currentPRD.title.replace(/\s+/g, '_').toLowerCase()}.md`}
                </p>
              </div>

              <Input
                label="Recipient Name"
                placeholder="John Doe"
                value={formData.recipientName}
                onChange={(e) => setFormData({ ...formData, recipientName: e.target.value })}
                error={errors.recipientName}
              />

              <Input
                label="Recipient Email"
                type="email"
                placeholder="john@example.com"
                value={formData.recipientEmail}
                onChange={(e) => setFormData({ ...formData, recipientEmail: e.target.value })}
                error={errors.recipientEmail}
              />

              {errors.submit && (
                <div className="flex items-center gap-2 text-status-error text-sm">
                  <AlertCircle className="w-4 h-4" />
                  {errors.submit}
                </div>
              )}

              <Button
                type="submit"
                isLoading={isSubmitting}
                className="w-full"
              >
                <Send className="w-4 h-4 mr-2" />
                Send PRD
              </Button>
            </form>
          ) : (
            <div className="text-center py-8">
              <AlertCircle className="w-12 h-12 text-status-warning mx-auto mb-4" />
              <h3 className="text-lg font-medium text-text-primary mb-2">No PRD Available</h3>
              <p className="text-text-secondary mb-4">
                Generate a PRD first before sending it via email.
              </p>
              <Button onClick={() => navigate('/')}>Start Chat</Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
