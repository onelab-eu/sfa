<?xml version="1.0" encoding="UTF-8"?>
<!--
  
  Copyright (c) 2014 Raytheon BBN Technologies
 
  Permission is hereby granted, free of charge, to any person obtaining
  a copy of this software and/or hardware specification (the "Work") to
  deal in the Work without restriction, including without limitation the
  rights to use, copy, modify, merge, publish, distribute, sublicense,
  and/or sell copies of the Work, and to permit persons to whom the Work
  is furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be
  included in all copies or substantial portions of the Work.
 
  THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
  OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
  IN THE WORK.

  Portions have this copyright:

  GENIPUBLIC-COPYRIGHT
  Copyright (c) 2008-2009 University of Utah and the Flux Group.
  All rights reserved.
  
-->
<!--
  GENI credential and privilege specification. The key points:
  
  * A credential is a set of privileges or a Ticket, each with a flag
    to indicate delegation is permitted. Or an ABAC RT0 statement.
  * A credential is signed and the signature included in the body of the
    document.
  * To support delegation, a credential will include its parent, and that
    blob will be signed. So, there will be multiple signatures in the
    document, each with a reference to the credential it signs.
  
  Default namespace = "http://www.geni.net/resources/credential/2"
-->
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" elementFormDefault="qualified" xmlns:sig="http://www.w3.org/2000/09/xmldsig#">
  <xs:include schemaLocation="protogeni-rspec-common.xsd"/>
  <xs:import namespace="http://www.w3.org/2000/09/xmldsig#" schemaLocation="sig.xsd"/>
  <xs:import namespace="http://www.w3.org/XML/1998/namespace" schemaLocation="xml.xsd"/>
  <xs:group name="anyelementbody">
    <xs:sequence>
      <xs:any minOccurs="0" maxOccurs="unbounded" processContents="skip"/>
    </xs:sequence>
  </xs:group>
  <xs:attributeGroup name="anyelementbody">
    <xs:anyAttribute processContents="skip"/>
  </xs:attributeGroup>
  <!-- This is where we get the definition of RSpec from -->
  <xs:element name="privilege">
    <xs:complexType>
      <xs:sequence>
        <xs:element ref="name"/>
        <xs:element name="can_delegate" type="xs:boolean"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
  <xs:element name="name">
    <xs:simpleType>
      <xs:restriction base="xs:string">
        <xs:minLength value="1"/>
      </xs:restriction>
    </xs:simpleType>
  </xs:element>
  <xs:element name="privileges"> <!-- For type 'privilege' only -->
    <xs:complexType>
      <xs:sequence>
        <xs:element minOccurs="0" maxOccurs="unbounded" ref="privilege"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
  <xs:element name="capability">
    <xs:complexType>
      <xs:sequence>
        <xs:element ref="name"/>
        <xs:element name="can_delegate">
          <xs:simpleType>
            <xs:restriction base="xs:token">
              <xs:enumeration value="0"/>
              <xs:enumeration value="1"/>
            </xs:restriction>
          </xs:simpleType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
  <xs:element name="capabilities"> <!-- For type 'capability' only -->
    <xs:complexType>
      <xs:sequence>
        <xs:element minOccurs="0" maxOccurs="unbounded" ref="capability"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
  <xs:element name="ticket"> <!-- For type 'ticket' only -->
    <xs:complexType mixed="true">
      <xs:sequence>
        <xs:element name="can_delegate" type="xs:boolean">
          <xs:annotation>
            <xs:documentation>Can the ticket be delegated?</xs:documentation>
          </xs:annotation>
        </xs:element>
        <xs:element ref="redeem_before"/>
        <xs:group ref="anyelementbody">
          <xs:annotation>
            <xs:documentation>A desciption of the resources that are being promised</xs:documentation>
          </xs:annotation>
        </xs:group>
      </xs:sequence>
      <xs:attributeGroup ref="anyelementbody"/>
    </xs:complexType>
  </xs:element>
  <xs:element name="redeem_before" type="xs:dateTime">
    <xs:annotation>
      <xs:documentation>The ticket must be "cashed in" by this date </xs:documentation>
    </xs:annotation>
  </xs:element>

  <!-- Elements used for type 'abac'. See http://groups.geni.net/geni/wiki/TIEDABACCredential -->
  <xs:element name="ABACprincipal">
    <xs:complexType>
      <xs:sequence>
	<xs:element name="keyid" type="xs:string"/> <!-- SHA1 hash of the principal's public key -->
	<xs:element name="mnemonic" type="xs:string" minOccurs="0" maxOccurs="1"/> <!-- EG principal's URN -->
      </xs:sequence>
    </xs:complexType>
  </xs:element>
  <!-- A single rt0 element is required for creds of type 'abac'. Must have a single 'head'
       and at least one 'tail'. -->
  <xs:element name="rt0">
    <xs:annotation>
      <xs:documentation>An ABAC RT0 statement, used only for type 'abac'.</xs:documentation>
    </xs:annotation>
    <xs:complexType>
      <xs:sequence>
	<xs:element name="version" type="xs:string" /> <!-- 1.1 for this schema -->
	<xs:element name="head">
	  <xs:complexType>
	    <xs:sequence>
	      <xs:element ref="ABACprincipal"/> <!-- Matching the cred signer -->
	      <xs:element name="role" type="xs:string"/>
	    </xs:sequence>
	  </xs:complexType>
	</xs:element>
	<xs:element name="tail" minOccurs="1" maxOccurs="unbounded">
	  <xs:complexType>
	    <xs:sequence>
	      <xs:element ref="ABACprincipal"/>
	      <xs:element name="role" type="xs:string" minOccurs="0" maxOccurs="1"/>
	      <xs:element name="linking_role" type="xs:string" minOccurs="0" 
			  maxOccurs="1"/>
	    </xs:sequence>
	  </xs:complexType>
	</xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
  <xs:element name="abac">
    <xs:annotation>
      <xs:documentation>An ABAC assertion containing a single RT0 statement, used only for type 'abac'.</xs:documentation>
    </xs:annotation>
    <xs:complexType>
      <xs:sequence>
	<xs:element minOccurs="1" maxOccurs="1" ref="rt0"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>

  <xs:element name="signatures">
    <xs:complexType>
      <xs:sequence>
        <xs:element maxOccurs="unbounded" ref="sig:Signature"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
  <xs:complexType name="credentials">
    <xs:annotation>
      <xs:documentation>A credential granting privileges or a ticket or making an ABAC assertion.</xs:documentation>
    </xs:annotation>
    <xs:sequence>
      <xs:element ref="credential"/>
    </xs:sequence>
  </xs:complexType>
  <xs:element name="credential">
    <xs:complexType>
      <xs:sequence>
        <xs:element ref="type"/>
        <xs:element ref="serial"/>
        <xs:element ref="owner_gid"/>
        <xs:element minOccurs="0" ref="owner_urn"/>
        <xs:element ref="target_gid"/>
        <xs:element minOccurs="0" ref="target_urn"/>
        <xs:element ref="uuid"/>
        <xs:element ref="expires"/>
        <xs:choice>
          <xs:annotation>
            <xs:documentation>Privileges or a ticket or an ABAC assertion</xs:documentation>
          </xs:annotation>
          <xs:element ref="privileges"/>
          <xs:element ref="ticket"/>
          <xs:element ref="capabilities"/>
	  <xs:element ref="abac"/>
        </xs:choice>
        <xs:element minOccurs="0" maxOccurs="unbounded" ref="extensions"/>
        <xs:element minOccurs="0" ref="parent"/>
      </xs:sequence>
      <xs:attribute ref="xml:id" use="required"/>
    </xs:complexType>
  </xs:element>
  <xs:element name="type">
    <xs:annotation>
      <xs:documentation>The type of this credential. Currently a Privilege set or a Ticket or ABAC.</xs:documentation>
    </xs:annotation>
    <xs:simpleType>
      <xs:restriction base="xs:token">
        <xs:enumeration value="privilege"/>
        <xs:enumeration value="ticket"/>
        <xs:enumeration value="capability"/>
        <xs:enumeration value="abac"/>
      </xs:restriction>
    </xs:simpleType>
  </xs:element>
  <xs:element name="serial" type="xs:string">
    <xs:annotation>
      <xs:documentation>A serial number.</xs:documentation>
    </xs:annotation>
  </xs:element>
  <xs:element name="owner_gid" type="xs:string">
    <xs:annotation>
      <xs:documentation>GID of the owner of this credential. </xs:documentation>
    </xs:annotation>
  </xs:element>
  <xs:element name="owner_urn" type="xs:string">
    <xs:annotation>
      <xs:documentation>URN of the owner. Not everyone can parse DER</xs:documentation>
    </xs:annotation>
  </xs:element>
  <xs:element name="target_gid" type="xs:string">
    <xs:annotation>
      <xs:documentation>GID of the target of this credential. </xs:documentation>
    </xs:annotation>
  </xs:element>
  <xs:element name="target_urn" type="xs:string">
    <xs:annotation>
      <xs:documentation>URN of the target.</xs:documentation>
    </xs:annotation>
  </xs:element>
  <xs:element name="uuid" type="xs:string">
    <xs:annotation>
      <xs:documentation>UUID of this credential</xs:documentation>
    </xs:annotation>
  </xs:element>
  <xs:element name="expires" type="xs:dateTime">
    <xs:annotation>
      <xs:documentation>Expires on in ISO8601 format but preferably RFC3339</xs:documentation>
    </xs:annotation>
  </xs:element>
  <xs:element name="extensions">
    <xs:annotation>
      <xs:documentation>Optional Extensions</xs:documentation>
    </xs:annotation>
    <xs:complexType mixed="true">
      <xs:group ref="anyelementbody"/>
      <xs:attributeGroup ref="anyelementbody"/>
    </xs:complexType>
  </xs:element>
  <xs:element name="parent" type="credentials">
    <xs:annotation>
      <xs:documentation>Parent that delegated to us</xs:documentation>
    </xs:annotation>
  </xs:element>
  <xs:element name="signed-credential">
    <xs:complexType>
      <xs:complexContent>
        <xs:extension base="credentials">
          <xs:sequence>
            <xs:element minOccurs="0" ref="signatures"/>
          </xs:sequence>
        </xs:extension>
      </xs:complexContent>
    </xs:complexType>
  </xs:element>
</xs:schema>
