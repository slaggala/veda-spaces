import { expect } from '@open-wc/testing';
import { emptyFilters, filtersToQuery, parseFilters } from '../src/modules/leads/filters.js';
import { primaryTransition, transitionBody, transitionRules, validateTransition } from '../src/modules/leads/transitions.js';

describe('status transition rules (04 §3)', () => {
  it('allows forward moves with an optional comment', () => {
    expect(validateTransition('NEW', 'SITE_VISIT', {})).to.deep.equal({});
    expect(transitionRules('NEW', 'SITE_VISIT')?.kind).to.equal('forward');
  });
  it('requires a comment to move back exactly one step and forbids larger jumps back', () => {
    expect(validateTransition('SITE_VISIT', 'CONTACTED', {})).to.have.property('comment');
    expect(validateTransition('SITE_VISIT', 'CONTACTED', { comment: 'Visit cancelled' })).to.deep.equal({});
    expect(transitionRules('NEGOTIATION', 'CONTACTED')).to.equal(null);
  });
  it('requires a lost reason, and a note for OTHER', () => {
    expect(validateTransition('CONTACTED', 'LOST', {})).to.have.property('lost_reason_code');
    expect(validateTransition('CONTACTED', 'LOST', { lost_reason_code: 'OTHER' })).to.have.property('lost_reason_note');
    expect(validateTransition('CONTACTED', 'LOST', { lost_reason_code: 'CHOSE_COMPETITOR' })).to.deep.equal({});
    expect(transitionRules('CONTACTED', 'LOST')?.cancelsPlanned).to.equal(true);
  });
  it('requires a comment for an early WON but not from NEGOTIATION/QUOTATION_SENT', () => {
    expect(validateTransition('NEW', 'WON', {})).to.have.property('comment');
    expect(validateTransition('NEGOTIATION', 'WON', {})).to.deep.equal({});
    expect(validateTransition('QUOTATION_SENT', 'WON', {})).to.deep.equal({});
  });
  it('treats reopen as lead.reopen with a required comment, and blocks WON↔LOST', () => {
    const r = transitionRules('LOST', 'CONTACTED');
    expect(r?.permission).to.equal('lead.reopen');
    expect(r?.commentRequired).to.equal(true);
    expect(transitionRules('WON', 'NEGOTIATION')?.kind).to.equal('reopen');
    expect(transitionRules('WON', 'LOST')).to.equal(null);
    expect(transitionRules('LOST', 'WON')).to.equal(null);
    expect(transitionRules('NEW', 'NEW')).to.equal(null);
  });
  it('builds the API body and picks the primary next step', () => {
    expect(transitionBody('LOST', { lost_reason_code: 'CHOSE_COMPETITOR', lost_reason_note: ' x ', comment: '' }))
      .to.deep.equal({ to_status: 'LOST', lost_reason_code: 'CHOSE_COMPETITOR', lost_reason_note: 'x' });
    expect(primaryTransition('SITE_VISIT', ['QUOTATION_SENT', 'LOST'])).to.equal('QUOTATION_SENT');
    expect(primaryTransition('SITE_VISIT', ['LOST'])).to.equal(null);
    expect(primaryTransition('WON', ['NEGOTIATION'])).to.equal(null);
  });
});

describe('lead filters ↔ URL query (08 §8.2)', () => {
  it('parses CSV lists, flags and dates 1:1 with the API parameters', () => {
    const f = parseFilters('?q=priya&status=NEW,CONTACTED&assigned_to=me&follow_up=overdue&created_on_from=2026-09-01&open=true&spam_status=SUSPECTED&page=2');
    expect(f.q).to.equal('priya');
    expect(f.status).to.deep.equal(['NEW', 'CONTACTED']);
    expect(f.assigned_to).to.deep.equal(['me']);
    expect(f.follow_up).to.equal('overdue');
    expect(f.created_on_from).to.equal('2026-09-01');
    expect(f.open).to.equal(true);
    expect(f.spam_status).to.deep.equal(['SUSPECTED']);
    expect(f.page).to.equal(2);
  });
  it('drops invalid values instead of sending them', () => {
    const f = parseFilters('?follow_up=yesterday&sort=-password&page=-3&page_size=5000&created_on_to=29/09/2026');
    expect(f.follow_up).to.equal('');
    expect(f.sort).to.equal('-created_on');
    expect(f.page).to.equal(1);
    expect(f.page_size).to.equal(25);
    expect(f.created_on_to).to.equal('');
  });
  it('round-trips and omits defaults', () => {
    const qs = '?q=anita&status=NEW&assigned_to=unassigned&sort=next_follow_up_on&page_size=50';
    expect(`?${filtersToQuery(parseFilters(qs)).toString()}`).to.equal(qs);
    expect(filtersToQuery(emptyFilters()).toString()).to.equal('');
  });
});
