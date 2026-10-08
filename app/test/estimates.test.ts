import { expect } from '@open-wc/testing';
import type { EstimateSelection } from '../src/core/api/types.js';
import { apiUnit, measurementRows, PACKAGES, rangeText, revisedSelections, rupees } from '../src/modules/leads/estimates.js';

const selections: EstimateSelection[] = [
  { room: 'MASTER_BEDROOM', product: 'WARDROBE', measurements: { WIDTH: { value: 6, unit: 'ft' } }, options: { DOOR: 'SLIDING' } },
  { room: 'KITCHEN', product: 'KITCHEN', measurements: {}, options: {} },
];

describe('Budgetary Estimate helpers (ADR-012)', () => {
  it('formats paise as rupees with Indian grouping', () => {
    expect(rupees(1_215_000_00)).to.equal('₹12,15,000');
    expect(rupees(null)).to.equal('—');
    expect(rangeText({ low_minor: 1_050_000_00, high_minor: 1_400_000_00 })).to.equal('₹10,50,000 – ₹14,00,000');
  });
  it('applies measurement edits for a revision and keeps options', () => {
    const out = revisedSelections(selections, { '0|WIDTH|ft': '8', '0|HEIGHT|ft': '7.5', '1|RUN|m': '3' });
    expect(out[0].measurements).to.deep.equal({ WIDTH: { value: 8, unit: 'ft' }, HEIGHT: { value: 7.5, unit: 'ft' } });
    expect(out[0].options).to.deep.equal({ DOOR: 'SLIDING' });
    expect(out[1].measurements).to.deep.equal({ RUN: { value: 3, unit: 'm' } });
    expect(selections[0].measurements).to.deep.equal({ WIDTH: { value: 6, unit: 'ft' } }, 'the original is not mutated');
  });
  it('an empty or non-positive edit returns the measurement to the typical size', () => {
    expect(revisedSelections(selections, { '0|WIDTH|ft': '' })[0].measurements).to.deep.equal({});
    expect(revisedSelections(selections, { '0|WIDTH|ft': '-2' })[0].measurements).to.deep.equal({});
  });
  it('keeps the unit kind of a typical area or count, so a revision is accepted', () => {
    expect(apiUnit('sq ft')).to.equal('sqft');
    expect(apiUnit('nos')).to.equal('nos');
    expect(apiUnit('ft')).to.equal('ft');
    const ceiling = { room: 'WHOLE_HOME', product: 'FALSE_CEILING', measurements: {}, options: {} };
    expect(measurementRows(ceiling, [{ name: 'AREA', unit: 'sqft' }])).to.deep.equal([
      { name: 'AREA', value: '', unit: 'sqft', typical: true },
    ]);
  });
  it('never offers Luxury for a staff revision (priced after a design consultation)', () => {
    expect([...PACKAGES]).to.deep.equal(['ESSENTIAL', 'PREMIUM']);
  });
  it('lists entered and typical measurements for the revision form', () => {
    expect(measurementRows(selections[0], ['HEIGHT'])).to.deep.equal([
      { name: 'WIDTH', value: '6', unit: 'ft', typical: false },
      { name: 'HEIGHT', value: '', unit: 'ft', typical: true },
    ]);
  });
});
