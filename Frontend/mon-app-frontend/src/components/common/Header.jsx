// src/components/common/Header.jsx

import React from 'react';
import { Navbar, Container, Nav, Button } from 'react-bootstrap';

const Header = ({ activeTab, setActiveTab }) => (
  <Navbar bg="white" expand="lg" className="shadow-sm border-bottom py-3">
    <Container fluid className="px-4 px-sm-6 px-lg-8">
      <div className="d-flex align-items-center">
        <div>
          <h1 className="h4 mb-0 text-dark">ONEE</h1>
          <p className="text-muted mb-0" style={{ fontSize: '0.875rem' }}>Suivi des Déplacements</p>
        </div>
      </div>
      <Navbar.Toggle aria-controls="basic-navbar-nav" />
      <Navbar.Collapse id="basic-navbar-nav" className="justify-content-end">
        <Nav className="ms-auto"> {/* ms-auto pushes content to the right */}
          {['missions', 'collaborateurs', 'vehicules', 'rapports'].map((tab) => (
            <Nav.Link
              as={Button} // Render Nav.Link as a Button to apply button styling
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`text-capitalize ${
                activeTab === tab
                  ? 'btn btn-primary-light text-primary' // Custom class for active state
                  : 'text-muted hover-link' // Custom class for hover effect
              }`}
              style={{
                borderRadius: '0.375rem', // Equivalent to rounded-md
                padding: '0.5rem 0.75rem', // Equivalent to px-3 py-2
                fontSize: '0.875rem', // Equivalent to text-sm
                fontWeight: '500', // Equivalent to font-medium
                transition: 'all 0.15s ease-in-out', // Equivalent to transition-colors
                backgroundColor: activeTab === tab ? '#e0f2fe' : 'transparent', // bg-blue-100
                color: activeTab === tab ? '#1d4ed8' : '#6c757d', // text-blue-700 / text-gray-500
              }}
            >
              {tab}
            </Nav.Link>
          ))}
        </Nav>
      </Navbar.Collapse>
    </Container>
  </Navbar>
);

export default Header;